from __future__ import annotations

import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from backend.core.config import settings
from tavily import TavilyClient

def tavily_search(query: str, max_results: int = 5) -> list[dict]:
    if not settings.tavily_api_key:
        return []
    client = TavilyClient(api_key=settings.tavily_api_key)
    resp = client.search(
        query=query,
        search_depth="basic",   # 1 credit
        max_results=max_results,
        include_answer=False,
    )
    return resp.get("results") or []

# ============================================================
# CONFIGURATION
# ============================================================

REQUEST_TIMEOUT = 10.0

# Browser fallback is used only for public social-profile pages whose
# useful content is rendered with JavaScript and therefore missing from
# a normal httpx response.
SOCIAL_BROWSER_TIMEOUT_MS = 15000
SOCIAL_BROWSER_WAIT_MS = 2500

# Maximum number of pages researched for one card.
# This prevents an endless crawl.
MAX_RESEARCH_PAGES = 15

# 0 = original website / QR page
# 1 = pages discovered from it
# 2 = pages discovered from those pages
MAX_RESEARCH_DEPTH = 2

# After direct crawling finishes, use Google Search grounding only
# for fields that are still missing. This is failure-safe: if search
# grounding is unavailable, normal enrichment still succeeds.
ENABLE_GOOGLE_SEARCH_FALLBACK = True

# Use the same Gemini model already configured for the backend.
WEB_RESEARCH_MODEL = settings.gemini_vlm_model


SOCIAL_DOMAINS = {
    "instagram_url": "instagram.com",
    "facebook_url": "facebook.com",
    "linkedin_url": "linkedin.com",
}


RESEARCH_SOCIAL_DOMAINS = (
    "instagram.com",
    "facebook.com",
    "fb.com",
    "linkedin.com",
)


TARGET_FIELDS = (
    "company_name",
    "owner_name",
    "designation",
    "address",
    "email",
    "phone",
    "gst_number",
    "website_url",
    "instagram_url",
    "facebook_url",
    "linkedin_url",
    "other_details",
)


# ============================================================
# REGEX
# ============================================================

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@"
    r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


PHONE_PATTERN = re.compile(
    r"(?<!\w)"
    r"(?:\+?\d[\d\s().-]{7,}\d)"
    r"(?!\w)"
)


GST_PATTERN = re.compile(
    r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b",
    re.IGNORECASE,
)


ADDRESS_LABEL_PATTERN = re.compile(
    r"(?:registered\s+(?:office|address)|business\s+address|"
    r"office\s+address|address)\s*[:\-]\s*(.+)",
    re.IGNORECASE,
)

PLACEHOLDER_MARKERS = (
    "@example.com",
    "@example.org",
    "@example.net",
    "lorem ipsum",
    "dummy address",
    "sample address",
)

# Reject known demo/theme contact values individually instead of
# rejecting the entire page. A real page can contain a stray demo
# value in a hidden/footer section and still contain valid business data.
PLACEHOLDER_PHONE_DIGITS = {
    "7031723412",
}

PLACEHOLDER_ADDRESS_MARKERS = (
    "7021 washington",
    "south new york",
    "new york, ny 10012",
)


class WebResearchResult(BaseModel):
    company_name: str | None = None
    owner_name: str | None = None
    designation: str | None = None
    address: str | None = None
    email: str | None = None
    phone: str | None = None
    gst_number: str | None = None
    website_url: str | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    linkedin_url: str | None = None
    other_details: str | None = None
    source_urls: list[str] = Field(default_factory=list)


# ============================================================
# EXISTING URL PROCESSOR
# ============================================================

def process_url(url: str) -> dict:
    """
    Basic URL processor.

    This function is kept because other parts of the
    application may already use it.
    """

    if not url:
        return {
            "company_name": None,
            "location": None,
            "email": None,
            "phone": None,
            "gst_number": None,
            "company_logo": None,
            "source_type": "url",
            "original_file_url": None,
        }

    normalized_url = normalize_url(url)

    if not normalized_url:
        return {
            "company_name": None,
            "location": None,
            "email": None,
            "phone": None,
            "gst_number": None,
            "company_logo": None,
            "source_type": "url",
            "original_file_url": url,
        }

    parsed = urlparse(normalized_url)

    domain = parsed.netloc

    if domain.startswith("www."):
        domain = domain[4:]

    return {
        "company_name": domain or None,
        "location": None,
        "email": None,
        "phone": None,
        "gst_number": None,
        "company_logo": None,
        "source_type": "url",
        "original_file_url": normalized_url,
    }


# ============================================================
# URL HELPERS
# ============================================================

def normalize_url(
    url: str | None,
) -> str | None:
    """
    Normalize a normal HTTP/HTTPS URL.

    Examples:

        www.example.com
        -> https://www.example.com

    Non-web schemes such as mailto:, tel: and javascript:
    are rejected.
    """

    if not url:
        return None

    url = url.strip()

    if not url:
        return None

    lower_url = url.lower()

    if lower_url.startswith(
        (
            "mailto:",
            "tel:",
            "javascript:",
            "data:",
            "file:",
        )
    ):
        return None

    if url.startswith("//"):
        url = f"https:{url}"

    if "://" not in url:
        url = f"https://{url}"

    parsed = urlparse(url)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return None

    if not parsed.netloc:
        return None

    # Remove #fragments so the same page is not
    # researched multiple times.
    parsed = parsed._replace(
        fragment=""
    )

    return urlunparse(parsed)


def get_domain(
    url: str,
) -> str:
    """
    Return clean domain without www.
    """

    parsed = urlparse(url)

    domain = (
        parsed.hostname
        or ""
    ).lower()

    if domain.startswith(
        "www."
    ):
        domain = domain[4:]

    return domain


def same_domain(
    first_url: str,
    second_url: str,
) -> bool:
    """
    Check whether two URLs belong
    to the same company website.
    """

    first_domain = get_domain(
        first_url
    )

    second_domain = get_domain(
        second_url
    )

    if (
        not first_domain
        or not second_domain
    ):
        return False

    return (
        first_domain == second_domain
        or first_domain.endswith(
            f".{second_domain}"
        )
        or second_domain.endswith(
            f".{first_domain}"
        )
    )


def is_social_url(
    url: str,
) -> bool:
    """
    Return True when the URL belongs to one of the
    supported social platforms.
    """

    domain = get_domain(url)

    return any(
        domain == social_domain
        or domain.endswith(
            f".{social_domain}"
        )
        for social_domain in RESEARCH_SOCIAL_DOMAINS
    )


def is_researchable_social_profile(
    url: str,
) -> bool:
    """
    Avoid crawling generic social-site pages, login pages,
    share dialogs, posts, reels, etc.

    We want company/person profile pages only.
    """

    if not is_social_url(url):
        return False

    parsed = urlparse(url)

    domain = get_domain(url)
    path = parsed.path.rstrip("/").lower()

    if not path:
        return False

    if "instagram.com" in domain:
        blocked = (
            "/p/",
            "/reel/",
            "/reels/",
            "/explore/",
            "/accounts/",
        )

        return not path.startswith(
            blocked
        )

    if (
        "facebook.com" in domain
        or "fb.com" in domain
    ):
        blocked = (
            "/login",
            "/dialog",
            "/share",
            "/sharer",
            "/help",
            "/privacy",
            "/plugins",
            "/watch",
            "/reel",
        )

        return not path.startswith(
            blocked
        )

    if "linkedin.com" in domain:
        return path.startswith(
            (
                "/company/",
                "/in/",
                "/school/",
            )
        )

    return False


def is_safe_public_url(
    url: str,
) -> bool:
    """
    Basic SSRF protection for the crawler.

    Reject localhost, loopback, private, link-local and
    other non-public IP addresses.
    """

    parsed = urlparse(url)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return False

    hostname = parsed.hostname

    if not hostname:
        return False

    hostname = hostname.lower()

    if hostname in {
        "localhost",
        "localhost.localdomain",
    }:
        return False

    try:
        direct_ip = ipaddress.ip_address(
            hostname
        )

        return direct_ip.is_global

    except ValueError:
        pass

    try:
        resolved = socket.getaddrinfo(
            hostname,
            None,
        )

    except socket.gaierror:
        return False

    if not resolved:
        return False

    for result in resolved:

        raw_ip = result[4][0]

        try:
            resolved_ip = ipaddress.ip_address(
                raw_ip
            )

        except ValueError:
            return False

        if not resolved_ip.is_global:
            return False

    return True


def is_allowed_research_url(
    url: str,
    base_url: str,
) -> bool:
    """
    Research only:
    - the official website domain
    - supported social profile pages

    Random third-party links are ignored.
    """

    if not is_safe_public_url(url):
        return False

    if same_domain(
        url,
        base_url,
    ):
        return True

    return is_researchable_social_profile(
        url
    )


# ============================================================
# CLEANERS
# ============================================================

def clean_text(
    value: str | None,
) -> str | None:

    if not value:
        return None

    value = " ".join(
        value.split()
    ).strip()

    return value or None


def clean_email(
    value: str | None,
) -> str | None:

    if not value:
        return None

    value = value.strip()

    if value.lower().startswith(
        "mailto:"
    ):
        value = value[7:]

    value = value.split("?")[0]

    match = EMAIL_PATTERN.search(
        value
    )

    if not match:
        return None

    email = match.group(0)

    domain = email.rsplit("@", 1)[-1].lower()

    if domain in {
        "example.com",
        "example.org",
        "example.net",
    }:
        return None

    return email


def clean_phone(
    value: str | None,
) -> str | None:

    if not value:
        return None

    value = value.strip()

    if value.lower().startswith(
        "tel:"
    ):
        value = value[4:]

    value = value.split("?")[0]

    digits = re.sub(
        r"\D",
        "",
        value,
    )

    if (
        len(digits) < 8
        or len(digits) > 15
    ):
        return None

    if digits in PLACEHOLDER_PHONE_DIGITS:
        return None

    return clean_text(
        value
    )


def append_unique(
    values: list[str],
    value: str | None,
) -> None:

    if not value:
        return

    if value not in values:
        values.append(
            value
        )


# ============================================================
# WEBSITE RESULT CONTAINER
# ============================================================

def empty_website_data() -> dict[str, Any]:
    """
    Temporary research results collected from:
    - official website
    - QR page
    - official social profiles
    """

    return {
        "company_names": [],
        "owner_names": [],
        "designations": [],

        "emails": [],
        "phones": [],
        "addresses": [],
        "gst_numbers": [],
        "descriptions": [],

        "instagram_url": None,
        "facebook_url": None,
        "linkedin_url": None,
    }


# ============================================================
# SOCIAL LINK EXTRACTION
# ============================================================

def detect_social_link(
    url: str,
    website_data: dict[str, Any],
) -> None:
    """
    Detect Instagram, Facebook
    and LinkedIn links.
    """

    domain = get_domain(
        url
    )

    if (
        "instagram.com" in domain
        and not website_data[
            "instagram_url"
        ]
    ):
        website_data[
            "instagram_url"
        ] = url

    elif (
        (
            "facebook.com" in domain
            or "fb.com" in domain
        )
        and not website_data[
            "facebook_url"
        ]
    ):
        website_data[
            "facebook_url"
        ] = url

    elif (
        "linkedin.com" in domain
        and not website_data[
            "linkedin_url"
        ]
    ):
        website_data[
            "linkedin_url"
        ] = url


# ============================================================
# JSON-LD ADDRESS
# ============================================================

def format_address(
    address: Any,
) -> str | None:
    """
    Convert JSON-LD address to text.
    """

    if isinstance(
        address,
        str,
    ):
        return clean_text(
            address
        )

    if not isinstance(
        address,
        dict,
    ):
        return None

    parts = [
        address.get(
            "streetAddress"
        ),
        address.get(
            "addressLocality"
        ),
        address.get(
            "addressRegion"
        ),
        address.get(
            "postalCode"
        ),
        address.get(
            "addressCountry"
        ),
    ]

    cleaned_parts: list[str] = []

    for part in parts:

        if not part:
            continue

        cleaned = clean_text(
            str(part)
        )

        if cleaned:
            cleaned_parts.append(
                cleaned
            )

    if not cleaned_parts:
        return None

    return ", ".join(
        cleaned_parts
    )


# ============================================================
# JSON-LD EXTRACTION
# ============================================================

def extract_json_ld(
    soup: BeautifulSoup,
    website_data: dict[str, Any],
) -> None:
    """
    Extract structured business information from JSON-LD.

    Useful fields may include:
    - company name
    - founder/person name
    - designation/job title
    - email
    - phone
    - address
    - description
    - social profiles
    - tax identifiers
    """

    scripts = soup.find_all(
        "script",
        attrs={
            "type": "application/ld+json"
        },
    )

    organization_types = {
        "organization",
        "corporation",
        "localbusiness",
        "professionalservice",
        "store",
        "legalservice",
        "financialservice",
        "realestateagent",
        "medicalbusiness",
        "automotivebusiness",
    }

    def get_types(
        value: dict[str, Any],
    ) -> set[str]:

        raw_type = value.get(
            "@type"
        )

        if isinstance(
            raw_type,
            str,
        ):
            return {
                raw_type.lower()
            }

        if isinstance(
            raw_type,
            list,
        ):
            return {
                str(item).lower()
                for item in raw_type
            }

        return set()

    def extract_person(
        person: Any,
    ) -> None:

        if isinstance(
            person,
            list,
        ):
            for item in person:
                extract_person(
                    item
                )

            return

        if not isinstance(
            person,
            dict,
        ):
            return

        name = clean_text(
            str(
                person.get(
                    "name"
                )
            )
            if person.get(
                "name"
            )
            else None
        )

        job_title = clean_text(
            str(
                person.get(
                    "jobTitle"
                )
            )
            if person.get(
                "jobTitle"
            )
            else None
        )

        append_unique(
            website_data[
                "owner_names"
            ],
            name,
        )

        append_unique(
            website_data[
                "designations"
            ],
            job_title,
        )

    def inspect(
        value: Any,
    ) -> None:

        if isinstance(
            value,
            list,
        ):

            for item in value:
                inspect(item)

            return

        if not isinstance(
            value,
            dict,
        ):
            return

        types_found = get_types(
            value
        )

        # --------------------------------------------
        # COMPANY / ORGANIZATION
        # --------------------------------------------

        if (
            types_found
            & organization_types
        ):

            company_name = clean_text(
                str(
                    value.get(
                        "name"
                    )
                )
                if value.get(
                    "name"
                )
                else None
            )

            append_unique(
                website_data[
                    "company_names"
                ],
                company_name,
            )

            description = clean_text(
                str(
                    value.get(
                        "description"
                    )
                )
                if value.get(
                    "description"
                )
                else None
            )

            append_unique(
                website_data[
                    "descriptions"
                ],
                description,
            )

            founder = (
                value.get(
                    "founder"
                )
                or value.get(
                    "founders"
                )
            )

            extract_person(
                founder
            )

            tax_id = (
                value.get(
                    "taxID"
                )
                or value.get(
                    "vatID"
                )
            )

            if tax_id:

                gst_match = GST_PATTERN.search(
                    str(tax_id).upper()
                )

                if gst_match:

                    append_unique(
                        website_data[
                            "gst_numbers"
                        ],
                        gst_match.group(0).upper(),
                    )

        # --------------------------------------------
        # PERSON
        # --------------------------------------------

        if (
            "person" in types_found
            and value.get(
                "jobTitle"
            )
        ):
            extract_person(
                value
            )

        # --------------------------------------------
        # EMAIL
        # --------------------------------------------

        email = clean_email(
            str(
                value.get(
                    "email"
                )
            )
            if value.get(
                "email"
            )
            else None
        )

        append_unique(
            website_data[
                "emails"
            ],
            email,
        )

        # --------------------------------------------
        # PHONE
        # --------------------------------------------

        phone = clean_phone(
            str(
                value.get(
                    "telephone"
                )
            )
            if value.get(
                "telephone"
            )
            else None
        )

        append_unique(
            website_data[
                "phones"
            ],
            phone,
        )

        # --------------------------------------------
        # ADDRESS
        # --------------------------------------------

        address = format_address(
            value.get(
                "address"
            )
        )

        append_unique(
            website_data[
                "addresses"
            ],
            address,
        )

        # --------------------------------------------
        # SOCIAL LINKS
        # --------------------------------------------

        same_as = value.get(
            "sameAs"
        )

        if isinstance(
            same_as,
            str,
        ):
            same_as = [
                same_as
            ]

        if isinstance(
            same_as,
            list,
        ):

            for social_url in same_as:

                if not isinstance(
                    social_url,
                    str,
                ):
                    continue

                normalized = normalize_url(
                    social_url
                )

                if normalized:

                    detect_social_link(
                        normalized,
                        website_data,
                    )

        # --------------------------------------------
        # RECURSIVE SEARCH
        # --------------------------------------------

        for child in value.values():

            if isinstance(
                child,
                (
                    dict,
                    list,
                ),
            ):
                inspect(
                    child
                )

    for script in scripts:

        raw_data = (
            script.string
            or script.get_text(
                strip=True
            )
        )

        if not raw_data:
            continue

        try:
            parsed_data = json.loads(
                raw_data
            )

        except (
            json.JSONDecodeError,
            TypeError,
        ):
            continue

        inspect(
            parsed_data
        )


# ============================================================
# HTML EXTRACTION
# ============================================================

def extract_html_data(
    soup: BeautifulSoup,
    page_url: str,
    website_data: dict[str, Any],
) -> None:
    """
    Extract useful information from normal HTML.

    Current fields:
    - email
    - phone
    - GST
    - social links
    - company name metadata
    - description metadata
    """

    # ========================================================
    # METADATA
    # ========================================================

    site_name_meta = soup.find(
        "meta",
        attrs={
            "property": "og:site_name"
        },
    )

    if site_name_meta:

        site_name = clean_text(
            str(
                site_name_meta.get(
                    "content",
                    "",
                )
            )
        )

        append_unique(
            website_data[
                "company_names"
            ],
            site_name,
        )

    description_meta = (
        soup.find(
            "meta",
            attrs={
                "name": "description"
            },
        )
        or soup.find(
            "meta",
            attrs={
                "property": "og:description"
            },
        )
    )

    if description_meta:

        description = clean_text(
            str(
                description_meta.get(
                    "content",
                    "",
                )
            )
        )

        if (
            description
            and len(description) <= 500
        ):

            append_unique(
                website_data[
                    "descriptions"
                ],
                description,
            )

    # ========================================================
    # LINKS
    # ========================================================

    for link in soup.find_all(
        "a",
        href=True,
    ):

        href = str(
            link.get(
                "href",
                "",
            )
        ).strip()

        if not href:
            continue

        # ----------------------------------------------------
        # EMAIL
        # ----------------------------------------------------

        if href.lower().startswith(
            "mailto:"
        ):

            append_unique(
                website_data[
                    "emails"
                ],
                clean_email(
                    href
                ),
            )

            continue

        # ----------------------------------------------------
        # PHONE
        # ----------------------------------------------------

        if href.lower().startswith(
            "tel:"
        ):

            append_unique(
                website_data[
                    "phones"
                ],
                clean_phone(
                    href
                ),
            )

            continue

        # ----------------------------------------------------
        # SOCIAL
        # ----------------------------------------------------

        absolute_url = urljoin(
            page_url,
            href,
        )

        normalized = normalize_url(
            absolute_url
        )

        if normalized:

            detect_social_link(
                normalized,
                website_data,
            )

    # ========================================================
    # PAGE TEXT
    # ========================================================

    page_text = soup.get_text(
        " ",
        strip=True,
    )

    # Do not reject the whole page just because one demo/template
    # value exists somewhere in the HTML. Individual emails, phones
    # and addresses are filtered below.

    # --------------------------------------------------------
    # EMAILS
    # --------------------------------------------------------

    emails = EMAIL_PATTERN.findall(
        page_text
    )

    for email in emails:

        append_unique(
            website_data[
                "emails"
            ],
            clean_email(
                email
            ),
        )

    # --------------------------------------------------------
    # PHONES
    # --------------------------------------------------------

    phones = PHONE_PATTERN.findall(
        page_text
    )

    for phone in phones:

        append_unique(
            website_data[
                "phones"
            ],
            clean_phone(
                phone
            ),
        )

    # --------------------------------------------------------
    # GST
    # --------------------------------------------------------

    gst_numbers = GST_PATTERN.findall(
        page_text.upper()
    )

    for gst_number in gst_numbers:

        append_unique(
            website_data[
                "gst_numbers"
            ],
            gst_number.upper(),
        )


def page_looks_like_template(
    soup: BeautifulSoup,
) -> bool:
    """
    Detect obvious demo/template contact data.

    Some ecommerce themes ship with sample contact information
    such as hello@example.com and a fake store address. Those
    values must never be used to enrich a real business card.
    """

    text = soup.get_text(
        " ",
        strip=True,
    ).lower()

    return any(
        marker in text
        for marker in PLACEHOLDER_MARKERS
    )


def _looks_like_real_address(
    value: str,
) -> bool:
    """
    Conservative address validation.

    This prevents UI text such as "Have a question? Contact us!"
    from being stored as an address while still allowing normal
    postal/business addresses.
    """

    lowered = value.lower()

    reject_phrases = (
        "contact us",
        "get in touch",
        "have a question",
        "have an question",
        "send us a message",
        "reach us",
        "learn more",
        "click here",
    )

    if any(
        phrase in lowered
        for phrase in reject_phrases
    ):
        return False

    # Strong postal signals.
    has_digit = bool(
        re.search(r"\d", value)
    )

    has_indian_pin = bool(
        re.search(
            r"\b[1-9][0-9]{5}\b",
            value,
        )
    )

    address_words = (
        "road",
        "rd",
        "street",
        "st",
        "avenue",
        "ave",
        "lane",
        "ln",
        "floor",
        "shop",
        "office",
        "building",
        "bldg",
        "market",
        "nagar",
        "society",
        "complex",
        "plaza",
        "tower",
        "industrial",
        "estate",
        "sector",
        "phase",
        "plot",
        "door",
        "block",
        "district",
        "city",
        "state",
        "gujarat",
        "india",
    )

    has_address_word = any(
        re.search(
            rf"\b{re.escape(word)}\b",
            lowered,
        )
        for word in address_words
    )

    comma_count = value.count(",")

    # Require meaningful address evidence. This intentionally prefers
    # precision over filling an address with generic page text.
    return (
        has_indian_pin
        or (
            has_digit
            and (
                has_address_word
                or comma_count >= 2
            )
        )
        or (
            has_address_word
            and comma_count >= 3
        )
    )


def _trim_address_candidate(
    value: str | None,
) -> str | None:
    """Keep one validated address value and remove trailing contact data."""

    value = clean_text(value)

    if not value:
        return None

    stop_labels = (
        "email:",
        "e-mail:",
        "phone:",
        "telephone:",
        "website:",
        "business hours",
        "busness hours",
        "monday",
    )

    lowered = value.lower()
    cut_at = len(value)

    for label in stop_labels:
        index = lowered.find(label)

        if index != -1:
            cut_at = min(
                cut_at,
                index,
            )

    value = value[
        :cut_at
    ].strip(
        " ,;|-•"
    )

    if (
        len(value) < 8
        or len(value) > 350
    ):
        return None

    lowered_value = value.lower()

    if any(
        marker in lowered_value
        for marker in PLACEHOLDER_ADDRESS_MARKERS
    ):
        return None

    if any(
        marker in lowered_value
        for marker in PLACEHOLDER_MARKERS
    ):
        return None

    if not _looks_like_real_address(
        value
    ):
        return None

    return value


def extract_visible_social_text(
    visible_text: str,
    website_data: dict[str, Any],
) -> None:
    """
    Extract contact information from browser-rendered social-page text.

    Facebook/Instagram/LinkedIn often return little useful information
    to plain HTTP requests even though the public browser page visibly
    contains the business phone, email or address.
    """

    if not visible_text:
        return

    # Email / phone extraction from the rendered page.
    for email in EMAIL_PATTERN.findall(
        visible_text
    ):
        append_unique(
            website_data["emails"],
            clean_email(email),
        )

    for phone in PHONE_PATTERN.findall(
        visible_text
    ):
        append_unique(
            website_data["phones"],
            clean_phone(phone),
        )

    # Preserve rendered line boundaries. A social profile may display
    # a multi-line address beside a map-pin icon without an "Address:"
    # label, so normal website selectors cannot find it.
    lines = [
        clean_text(line)
        for line in visible_text.splitlines()
    ]

    lines = [
        line
        for line in lines
        if line
    ]

    for index in range(
        len(lines)
    ):
        # Try the current line and a small window of following lines.
        # This catches addresses visually wrapped over 2-3 lines.
        for width in (
            1,
            2,
            3,
        ):
            end_index = index + width

            if end_index > len(lines):
                continue

            candidate = " ".join(
                lines[
                    index:end_index
                ]
            )

            address = _trim_address_candidate(
                candidate
            )

            if address:
                append_unique(
                    website_data["addresses"],
                    address,
                )


def _browser_fallback_available() -> bool:
    return async_playwright is not None


async def fetch_rendered_social_page(
    url: str,
) -> tuple[str, str] | None:
    """
    Render a public social-profile page in Chromium.

    This is a fallback only. Normal websites continue to use httpx.
    If Playwright is unavailable, blocked, or a login wall hides the
    public data, enrichment simply continues without breaking scanning.
    """

    if not _browser_fallback_available():
        return None

    if not is_researchable_social_profile(
        url
    ):
        return None

    browser = None

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
            )

            context = await browser.new_context(
                viewport={
                    "width": 1440,
                    "height": 1000,
                },
                locale="en-US",
                user_agent=(
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
            )

            page = await context.new_page()

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=SOCIAL_BROWSER_TIMEOUT_MS,
            )

            await page.wait_for_timeout(
                SOCIAL_BROWSER_WAIT_MS
            )

            html = await page.content()

            visible_text = await page.locator(
                "body"
            ).inner_text(
                timeout=SOCIAL_BROWSER_TIMEOUT_MS,
            )

            await context.close()
            await browser.close()
            browser = None

            return (
                html,
                visible_text,
            )

    except Exception:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass

        return None


# ============================================================
# ADDRESS EXTRACTION
# ============================================================

def extract_addresses(
    soup: BeautifulSoup,
    website_data: dict[str, Any],
) -> None:
    """
    Extract addresses from structured containers and labelled text.

    Placeholder/demo address candidates are rejected individually,
    while valid addresses on the same page are still accepted.
    """

    # Standard HTML <address> tag.
    for address_element in soup.find_all(
        "address"
    ):

        address = _trim_address_candidate(
            address_element.get_text(
                " ",
                strip=True,
            )
        )

        append_unique(
            website_data[
                "addresses"
            ],
            address,
        )

    # Common address/location containers.
    selectors = [
        '[itemprop="address"]',
        '[class*="address"]',
        '[id*="address"]',
        '[class*="location"]',
        '[id*="location"]',
    ]

    for selector in selectors:

        for element in soup.select(
            selector
        ):

            address = _trim_address_candidate(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            append_unique(
                website_data[
                    "addresses"
                ],
                address,
            )

    # Many legal/terms pages put the address in an ordinary <p>
    # rather than an element whose class contains "address".
    # Preserve line boundaries and look for explicit labels.
    lines = [
        clean_text(str(item))
        for item in soup.stripped_strings
    ]

    lines = [
        line
        for line in lines
        if line
    ]

    for index, line in enumerate(lines):

        match = ADDRESS_LABEL_PATTERN.search(
            line
        )

        if match:
            address = _trim_address_candidate(
                match.group(1)
            )

            append_unique(
                website_data[
                    "addresses"
                ],
                address,
            )

        # Themes often render a heading such as "OUR STORE" and
        # place the physical address on the next line.
        if line.strip().lower() in {
            "our store",
            "store address",
            "registered office",
            "business address",
            "office address",
        }:

            if index + 1 < len(lines):
                address = _trim_address_candidate(
                    lines[index + 1]
                )

                append_unique(
                    website_data[
                        "addresses"
                    ],
                    address,
                )

    # Fallback over the complete visible text. This catches pages where
    # an icon/span separates the label from the address, for example:
    # "📍 Address: Raghuvir ... Surat, GJ, 395010, IN".
    page_text = soup.get_text(" ", strip=True)

    for match in ADDRESS_LABEL_PATTERN.finditer(page_text):
        address = _trim_address_candidate(
            match.group(1)
        )

        append_unique(
            website_data["addresses"],
            address,
        )


# ============================================================
# FIND USEFUL INTERNAL PAGES
# ============================================================

def discover_company_pages(
    soup: BeautifulSoup,
    current_url: str,
    base_url: str,
) -> list[str]:
    """
    Discover useful company pages.

    Example:
        /contact
        /contact-us
        /about
        /about-us
        /location
    """

    keywords = (
        "contact",
        "contact-us",
        "about",
        "about-us",
        "location",
        "reach-us",
        "reach",
        "get-in-touch",
        # Legal/policy pages often contain the registered business
        # name and address even when the contact page is incomplete.
        "terms",
        "terms-of-service",
        "privacy",
        "policy",
        "refund",
        "shipping",
        "return",
        "legal",
        "imprint",
    )

    pages: list[str] = []

    for link in soup.find_all(
        "a",
        href=True,
    ):

        href = str(
            link.get(
                "href",
                "",
            )
        ).strip()

        link_text = clean_text(
            link.get_text(
                " ",
                strip=True,
            )
        ) or ""

        if not href:
            continue

        href_lower = href.lower()

        text_lower = (
            link_text.lower()
        )

        useful = any(
            keyword in href_lower
            or keyword in text_lower
            for keyword in keywords
        )

        if not useful:
            continue

        absolute_url = urljoin(
            current_url,
            href,
        )

        normalized = normalize_url(
            absolute_url
        )

        if not normalized:
            continue

        # IMPORTANT:
        # Only stay on the official website.
        if not same_domain(
            normalized,
            base_url,
        ):
            continue

        if normalized not in pages:
            pages.append(
                normalized
            )

    return pages


# ============================================================
# PICK BEST RESULT
# ============================================================

def pick_email(
    emails: list[str],
) -> str | None:

    if not emails:
        return None

    preferred = (
        "info@",
        "contact@",
        "hello@",
        "sales@",
        "support@",
    )

    for prefix in preferred:

        for email in emails:

            if email.lower().startswith(
                prefix
            ):
                return email

    return emails[0]


def pick_phone(
    phones: list[str],
) -> str | None:

    if not phones:
        return None

    return phones[0]


def pick_address(
    addresses: list[str],
) -> str | None:

    if not addresses:
        return None

    return addresses[0]


# ============================================================
# RESEARCH LOOP HELPERS
# ============================================================

def discover_research_links(
    soup: BeautifulSoup,
    current_url: str,
    base_url: str,
    website_data: dict[str, Any],
) -> list[str]:
    """
    Discover the next useful pages to research.

    We only follow:
    1. useful pages on the official website
    2. official-looking social profile URLs
    3. links from a social profile back to the official website
    """

    discovered: list[str] = []

    # --------------------------------------------------------
    # USEFUL OFFICIAL WEBSITE PAGES
    # --------------------------------------------------------

    if same_domain(
        current_url,
        base_url,
    ):

        internal_pages = discover_company_pages(
            soup,
            current_url,
            base_url,
        )

        for page_url in internal_pages:

            if page_url not in discovered:
                discovered.append(
                    page_url
                )

    # --------------------------------------------------------
    # SOCIAL PROFILES ALREADY FOUND DURING EXTRACTION
    # --------------------------------------------------------

    for field in (
        "instagram_url",
        "facebook_url",
        "linkedin_url",
    ):

        social_url = website_data.get(
            field
        )

        if (
            social_url
            and social_url not in discovered
            and is_researchable_social_profile(
                social_url
            )
        ):
            discovered.append(
                social_url
            )

    # --------------------------------------------------------
    # LINKS FOUND ON CURRENT PAGE
    # --------------------------------------------------------

    for link in soup.find_all(
        "a",
        href=True,
    ):

        href = str(
            link.get(
                "href",
                "",
            )
        ).strip()

        if not href:
            continue

        absolute_url = urljoin(
            current_url,
            href,
        )

        normalized = normalize_url(
            absolute_url
        )

        if not normalized:
            continue

        # Social -> official website.
        if (
            is_social_url(
                current_url
            )
            and same_domain(
                normalized,
                base_url,
            )
        ):

            if normalized not in discovered:
                discovered.append(
                    normalized
                )

            continue

        # Official website -> social profile.
        if (
            same_domain(
                current_url,
                base_url,
            )
            and is_researchable_social_profile(
                normalized
            )
        ):

            if normalized not in discovered:
                discovered.append(
                    normalized
                )

            continue

        # One social profile may directly link to another
        # official social profile.
        if (
            is_social_url(
                current_url
            )
            and is_researchable_social_profile(
                normalized
            )
        ):

            if normalized not in discovered:
                discovered.append(
                    normalized
                )

    return discovered


def merge_research_data(
    enriched: dict[str, Any],
    website_data: dict[str, Any],
    base_url: str,
) -> None:
    """
    Fill only missing fields.

    Values already detected directly from the card
    keep highest priority.
    """

    # --------------------------------------------------------
    # WEBSITE
    # --------------------------------------------------------

    if (
        not enriched.get(
            "website_url"
        )
        and not is_social_url(
            base_url
        )
    ):
        enriched[
            "website_url"
        ] = base_url

    # --------------------------------------------------------
    # COMPANY NAME
    # --------------------------------------------------------

    discovered_company = (
        website_data[
            "company_names"
        ][0]
        if website_data[
            "company_names"
        ]
        else None
    )

    current_company = enriched.get(
        "company_name"
    )

    # process_url() uses the domain as a temporary
    # company_name. For URL-only processing, allow a real
    # researched company name to replace that placeholder.
    domain_placeholder = (
        get_domain(
            base_url
        )
        if base_url
        else None
    )

    if (
        not current_company
        or (
            enriched.get(
                "source_type"
            ) == "url"
            and current_company == domain_placeholder
        )
    ):

        if discovered_company:
            enriched[
                "company_name"
            ] = discovered_company

    # --------------------------------------------------------
    # OWNER / PERSON
    # --------------------------------------------------------

    if (
        not enriched.get(
            "owner_name"
        )
        and website_data[
            "owner_names"
        ]
    ):
        enriched[
            "owner_name"
        ] = website_data[
            "owner_names"
        ][0]

    # --------------------------------------------------------
    # DESIGNATION
    # --------------------------------------------------------

    if (
        not enriched.get(
            "designation"
        )
        and website_data[
            "designations"
        ]
    ):
        enriched[
            "designation"
        ] = website_data[
            "designations"
        ][0]

    # --------------------------------------------------------
    # EMAIL
    # --------------------------------------------------------

    if not enriched.get(
        "email"
    ):
        enriched[
            "email"
        ] = pick_email(
            website_data[
                "emails"
            ]
        )

    # --------------------------------------------------------
    # PHONE
    # --------------------------------------------------------

    if not enriched.get(
        "phone"
    ):
        enriched[
            "phone"
        ] = pick_phone(
            website_data[
                "phones"
            ]
        )

    # --------------------------------------------------------
    # ADDRESS
    # --------------------------------------------------------

    if not enriched.get(
        "address"
    ):
        enriched[
            "address"
        ] = pick_address(
            website_data[
                "addresses"
            ]
        )

    # --------------------------------------------------------
    # GST
    # --------------------------------------------------------

    if (
        not enriched.get(
            "gst_number"
        )
        and website_data[
            "gst_numbers"
        ]
    ):
        enriched[
            "gst_number"
        ] = website_data[
            "gst_numbers"
        ][0]

    # --------------------------------------------------------
    # SOCIAL PROFILES
    # --------------------------------------------------------

    for field in (
        "instagram_url",
        "facebook_url",
        "linkedin_url",
    ):

        if not enriched.get(
            field
        ):
            enriched[
                field
            ] = website_data.get(
                field
            )

    # --------------------------------------------------------
    # OTHER DETAILS
    # --------------------------------------------------------

    if (
        not enriched.get(
            "other_details"
        )
        and website_data[
            "descriptions"
        ]
    ):

        enriched[
            "other_details"
        ] = website_data[
            "descriptions"
        ][0]


def research_complete(
    enriched: dict[str, Any],
) -> bool:
    """
    Stop early only when every target field is filled.
    """

    return all(
        enriched.get(
            field
        )
        not in (
            None,
            "",
        )
        for field in TARGET_FIELDS
    )


# ============================================================
# WEBSITE / QR URL SELECTION
# ============================================================

def get_seed_urls(
    card_data: dict[str, Any],
) -> list[str]:
    """
    Use:

    1. Website detected from card
    2. QR URL when it belongs to the same domain
    """

    seed_urls: list[str] = []

    website_url = normalize_url(
        card_data.get(
            "website_url"
        )
    )

    qr_url = normalize_url(
        card_data.get(
            "qr_raw"
        )
    )

    # --------------------------------------------------------
    # WEBSITE
    # --------------------------------------------------------

    if website_url:
        seed_urls.append(
            website_url
        )

    # --------------------------------------------------------
    # QR URL
    # --------------------------------------------------------

    if (
        qr_url
        and qr_url not in seed_urls
    ):

        if (
            not website_url
            or same_domain(
                qr_url,
                website_url,
            )
        ):
            seed_urls.append(
                qr_url
            )

    return seed_urls


# ============================================================
# GOOGLE SEARCH FALLBACK
# ============================================================

def _missing_research_fields(
    card: dict[str, Any],
) -> list[str]:
    """Return fields that still need public-web research."""

    return [
        field
        for field in TARGET_FIELDS
        if card.get(field) in (
            None,
            "",
        )
    ]

# ============================================================
# WEBSITE DISCOVERY (when card has no website / QR)
# ============================================================

# ============================================================
# WEBSITE DISCOVERY (when card has no website / QR)
# Uses Tavily only — no Gemini search / grounding
# ============================================================

def _tavily_search(query: str, max_results: int = 8) -> list[dict]:
    """Run a free-tier Tavily web search. Returns list of result dicts."""
    api_key = getattr(settings, "tavily_api_key", None)
    if not api_key:
        print("TAVILY: no api key configured")
        return []

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        resp = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=False,
        )
        return resp.get("results") or []
    except Exception as exc:
        print("TAVILY SEARCH ERROR:", repr(exc))
        return []


def _build_discovery_query(card: dict[str, Any]) -> str:
    """
    Build search query for official website.
    Prefer: company/owner name + phone (strongest identity pair).
    """
    company = (card.get("company_name") or "").strip()
    owner = (card.get("owner_name") or "").strip()
    phone = (card.get("phone") or "").strip()

    # Clean phone a bit for search (keep digits and +)
    phone_clean = re.sub(r"[^\d+]", "", phone) if phone else ""

    name = company or owner
    if not name and not phone_clean:
        # fallback: whatever else we have
        parts = []
        for key in ("email", "gst_number", "address"):
            value = card.get(key)
            if value not in (None, ""):
                parts.append(str(value).strip())
        return (" ".join(parts) + " official website").strip() if parts else ""

    parts: list[str] = []

    if name:
        parts.append(name)
    if phone_clean:
        parts.append(phone_clean)

    # If we have both name and phone → strongest query
    # If only one → still search with what we have
    parts.append("official website")

    return " ".join(parts)


def _score_website_candidate(
    url: str,
    card: dict[str, Any],
) -> int:
    """
    Higher score = better match for official website.
    Reject pure social profiles.
    Prefer domains that look related to company / email.
    """
    if not url or is_social_url(url):
        return -1

    domain = get_domain(url) or ""
    if not domain:
        return -1

    score = 1
    domain_lower = domain.lower()

    company = (card.get("company_name") or "").lower().strip()
    if company:
        # rough token match, e.g. "Acme Foods" vs acme-foods.com
        tokens = [
            t for t in re.split(r"[^a-z0-9]+", company) if len(t) >= 3
        ]
        for t in tokens:
            if t in domain_lower:
                score += 5

    email = clean_email(card.get("email")) if "clean_email" in dir() else None
    if not email:
        raw = card.get("email")
        if raw and "@" in str(raw):
            email = str(raw).strip().lower()

    if email and "@" in email:
        email_domain = email.split("@", 1)[1].lower()
        public_mail = {
            "gmail.com", "yahoo.com", "yahoo.co.in", "hotmail.com",
            "outlook.com", "live.com", "icloud.com", "me.com",
            "aol.com", "protonmail.com", "proton.me", "rediffmail.com",
            "ymail.com", "mail.com", "zoho.com",
        }
        if email_domain not in public_mail:
            if domain_lower == email_domain or domain_lower.endswith(
                "." + email_domain
            ):
                score += 20
            elif email_domain.split(".")[0] in domain_lower:
                score += 8

    # Prefer cleaner homepage-looking URLs
    path = (urlparse(url).path or "").rstrip("/")
    if path in ("", "/"):
        score += 3

    return score

def _normalize_phone_digits(value: str | None) -> str:
    """Keep digits only."""
    if not value:
        return ""
    return re.sub(r"\D", "", str(value))


def _phone_appears_on_page(card_phone: str, page_text: str) -> bool:
    """
    True if card phone is on the page.
    Uses last 10 digits so +91 / spaces / dashes still match.
    """
    card_digits = _normalize_phone_digits(card_phone)
    if len(card_digits) < 10:
        return False

    needle = card_digits[-10:]
    page_digits = _normalize_phone_digits(page_text)
    return needle in page_digits


async def _page_contains_card_phone(
    url: str,
    card_phone: str,
) -> bool:
    """
    Fetch homepage HTML and check for card phone.
    Plain HTTP only (no Playwright, no extra API).
    """
    if not card_phone or not url:
        return False

    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; CardScanner/1.0)"
                )
            },
        ) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                return False
            return _phone_appears_on_page(card_phone, resp.text or "")
    except Exception as exc:
        print("PHONE CHECK FETCH ERROR:", repr(exc))
        return False

async def discover_website_from_card(
    card: dict[str, Any],
) -> str | None:
    """
    When the scanned card has no website_url / usable QR URL,
    use Tavily web search (free tier) to find the official
    business website from identity clues already on the card.

    Returns a normalized website URL or None.
    Does NOT use Gemini / Google Search grounding.
    """

    query = _build_discovery_query(card)
    if not query:
        return None

    results = _tavily_search(query, max_results=8)
    if not results:
        return None

    best_url: str | None = None
    best_score = 0

    for item in results:
        raw_url = item.get("url") or ""
        website_url = normalize_url(raw_url)
        if not website_url:
            continue

        score = _score_website_candidate(website_url, card)
        if score > best_score:
            best_score = score
            best_url = website_url

    if best_score <= 20:
        return None

    return best_url

def _identity_summary(
    card: dict[str, Any],
) -> str:
    """Build strong identity clues so search does not mix companies."""

    keys = (
        "company_name",
        "owner_name",
        "designation",
        "website_url",
        "email",
        "phone",
        "gst_number",
        "address",
        "instagram_url",
        "facebook_url",
        "linkedin_url",
    )

    lines: list[str] = []

    for key in keys:
        value = card.get(key)

        if value not in (
            None,
            "",
        ):
            lines.append(
                f"{key}: {value}"
            )

    return "\n".join(lines)


def _merge_web_search_result(
    enriched: dict[str, Any],
    result: WebResearchResult,
) -> None:
    """
    Merge only missing fields returned by grounded web research.

    Existing card/website values always keep priority.
    """

    values = result.model_dump()

    # Normal text fields.
    for field in (
        "company_name",
        "owner_name",
        "designation",
        "other_details",
    ):
        if not enriched.get(field):
            value = clean_text(
                values.get(field)
            )

            if value:
                enriched[field] = value

    # Email.
    if not enriched.get("email"):
        email = clean_email(
            values.get("email")
        )

        if email:
            enriched["email"] = email

    # Phone.
    if not enriched.get("phone"):
        phone = clean_phone(
            values.get("phone")
        )

        if phone:
            enriched["phone"] = phone

    # Address.
    if not enriched.get("address"):
        address = _trim_address_candidate(
            values.get("address")
        )

        if address:
            enriched["address"] = address

    # GST.
    if not enriched.get("gst_number"):
        raw_gst = values.get("gst_number")

        if raw_gst:
            match = GST_PATTERN.search(
                str(raw_gst).upper()
            )

            if match:
                enriched["gst_number"] = (
                    match.group(0).upper()
                )

    # Website.
    if not enriched.get("website_url"):
        website_url = normalize_url(
            values.get("website_url")
        )

        if website_url:
            enriched["website_url"] = website_url

    # Social profiles: validate platform before accepting.
    social_fields = {
        "instagram_url": "instagram.com",
        "facebook_url": "facebook.com",
        "linkedin_url": "linkedin.com",
    }

    for field, expected_domain in social_fields.items():
        if enriched.get(field):
            continue

        url = normalize_url(
            values.get(field)
        )

        if not url:
            continue

        domain = get_domain(url)

        if (
            domain == expected_domain
            or domain.endswith(
                f".{expected_domain}"
            )
            or (
                field == "facebook_url"
                and (
                    domain == "fb.com"
                    or domain.endswith(".fb.com")
                )
            )
        ):
            enriched[field] = url


# ============================================================
# TAVILY + GEMINI PARSE FALLBACK (no Google Search tool)
# ============================================================

def _build_missing_fields_query(
    card: dict[str, Any],
    missing: list[str],
) -> str:
    """Search query from identity clues + what is still missing."""
    identity_parts: list[str] = []

    for key in (
        "company_name",
        "owner_name",
        "phone",
        "email",
        "gst_number",
        "address",
        "website_url",
    ):
        value = card.get(key)
        if value not in (None, ""):
            identity_parts.append(str(value).strip())

    missing_hint = " ".join(missing)
    base = " ".join(identity_parts)

    if not base:
        return ""

    return f"{base} {missing_hint} contact official website".strip()


def _format_tavily_results_for_prompt(results: list[dict]) -> str:
    """Turn Tavily hits into plain text for Gemini to parse."""
    blocks: list[str] = []

    for i, item in enumerate(results, start=1):
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        content = (item.get("content") or "").strip()
        blocks.append(
            f"[{i}] title: {title}\n"
            f"url: {url}\n"
            f"snippet: {content}"
        )

    return "\n\n".join(blocks) if blocks else "No search results."


async def research_missing_fields_with_google(
    enriched: dict[str, Any],
) -> dict[str, Any]:
    """
    Fill still-missing fields using:
      1) Tavily web search (search only)
      2) Gemini structured parse of those results (NO google_search tool)

    Existing card values always keep priority.
    If Tavily or Gemini fails, return current data unchanged.
    """

    if not ENABLE_GOOGLE_SEARCH_FALLBACK:
        return enriched

    missing = _missing_research_fields(enriched)
    if not missing:
        return enriched

    # Need at least one strong identity clue.
    if not any(
        enriched.get(field)
        for field in (
            "company_name",
            "website_url",
            "email",
            "phone",
            "instagram_url",
            "facebook_url",
            "linkedin_url",
        )
    ):
        return enriched

    query = _build_missing_fields_query(enriched, missing)
    if not query:
        return enriched

    # ---- 1) Tavily search only ----
    results = _tavily_search(query, max_results=8)
    if not results:
        return enriched

    search_text = _format_tavily_results_for_prompt(results)

    prompt = f"""
Research this exact business using ONLY the search results below.
Fill ONLY the fields that are currently missing.

Known identity clues:
{_identity_summary(enriched)}

Missing fields:
{', '.join(missing)}

Search results:
{search_text}

Research rules:
1. Make sure every result belongs to the SAME business.
2. Prefer the official website, official legal/terms/contact pages, and
   official social profiles.
3. Cross-check company name, website domain, email, phone, address/city,
   GST/tax identity, and social profile names before accepting a value.
4. Ignore demo/theme/template data such as example.com, lorem ipsum, sample
   US store addresses, or generic placeholder phone numbers.
5. Do not invent a value. Return null when it cannot be verified.
6. Do not replace or contradict any known value above.
7. For other_details, return only a short useful company description or legal
   business name if verified.
8. website_url must be a full http(s) URL when present.
"""

    try:
        client = genai.Client(api_key=settings.gemini_api_key)

        try:
            # IMPORTANT: no tools / no Google Search grounding
            response = await client.aio.models.generate_content(
                model=WEB_RESEARCH_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=WebResearchResult,
                    temperature=0.1,
                ),
            )
        finally:
            await client.aio.aclose()
            client.close()

        if not response.text:
            return enriched

        result = WebResearchResult.model_validate_json(response.text)
        _merge_web_search_result(enriched, result)

    except Exception as exc:
        print("TAVILY+GEMINI PARSE ENRICHMENT ERROR:", repr(exc))

    return enriched


# ============================================================
# MAIN RECURSIVE RESEARCH / ENRICHMENT
# ============================================================

async def enrich_business_card(
    card_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Research a business using the strongest links already
    available from the card.

    Flow:

    1. Start with website / QR URL.
    2. Research official website pages.
    3. Discover Instagram / Facebook / LinkedIn.
    4. Research those profile URLs when their public HTML
       is available.
    5. Discover useful new links.
    6. Repeat until:
       - target fields are filled, or
       - page/depth limits are reached.

    IMPORTANT:
    Existing information extracted directly from the card
    always keeps priority.
    """

    # Never modify the original scan result.
    enriched = dict(
        card_data
    )

    # ========================================================
    # INITIAL RESEARCH URLS
    # ========================================================

    seed_urls = get_seed_urls(
        card_data
    )

    # NO WEBSITE / QR ON CARD → discover website for free
# using Gemini + Google Search grounding from name,
# phone, email, company, GST, socials, etc.
# Once found, continue with the normal crawl logic.
    # ----------------------------------------------------
    # NO WEBSITE / QR ON CARD → discover website via Tavily
    # Once found, continue with the normal crawl logic.
    # If not found → return as-is (no extra field search).
    # ----------------------------------------------------
    if not seed_urls:
        discovered_website = await discover_website_from_card(
            enriched
        )

        if discovered_website:
            enriched["website_url"] = discovered_website
            seed_urls = [discovered_website]
        else:
            return enriched

    # Prefer a non-social URL as the official base website.
    base_url = next(
        (
            url
            for url in seed_urls
            if not is_social_url(
                url
            )
        ),
        seed_urls[0],
    )

    # ========================================================
    # RESEARCH RESULTS
    # ========================================================

    website_data = (
        empty_website_data()
    )

    # Queue item:
    #
    # (url, depth)
    #
    # depth 0 = initial website / QR
    # depth 1 = discovered page/social profile
    # depth 2 = discovered from depth 1
    queue: list[
        tuple[
            str,
            int,
        ]
    ] = [
        (
            url,
            0,
        )
        for url in seed_urls
    ]

    # Proactively try common business-information pages on the official
    # domain. 404s are harmless and skipped. This helps ecommerce sites
    # where legal pages contain the real registered company/address while
    # the visible Contact page still contains theme/demo data.
    parsed_base = urlparse(base_url)
    site_root = f"{parsed_base.scheme}://{parsed_base.netloc}"

    common_paths = (
        "/pages/contact",
        "/pages/contact-us",
        "/pages/about",
        "/pages/about-us",
        "/policies/terms-of-service",
        "/policies/privacy-policy",
        "/policies/refund-policy",
        "/policies/shipping-policy",
    )

    for path in common_paths:
        candidate = normalize_url(
            urljoin(site_root, path)
        )

        if (
            candidate
            and candidate not in {url for url, _ in queue}
        ):
            queue.append((candidate, 1))

    visited: set[str] = set()

    # ========================================================
    # REQUEST HEADERS
    # ========================================================

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "*/*;q=0.8"
        ),
        "Accept-Language": (
            "en-US,en;q=0.9"
        ),
    }

    # ========================================================
    # RESEARCH LOOP
    # ========================================================

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers=headers,
    ) as client:

        while (
            queue
            and len(visited)
            < MAX_RESEARCH_PAGES
        ):

            current_url, depth = (
                queue.pop(0)
            )

            current_url = normalize_url(
                current_url
            )

            if not current_url:
                continue

            if depth > MAX_RESEARCH_DEPTH:
                continue

            if current_url in visited:
                continue

            # Only official-site pages and supported
            # social profile URLs may be researched.
            if not is_allowed_research_url(
                current_url,
                base_url,
            ):
                continue

            visited.add(
                current_url
            )

            # =================================================
            # DOWNLOAD PAGE
            # =================================================

            try:

                response = await client.get(
                    current_url
                )

                response.raise_for_status()

            except httpx.HTTPError:
                continue

            # =================================================
            # CHECK CONTENT TYPE
            # =================================================

            content_type = (
                response.headers.get(
                    "content-type",
                    "",
                ).lower()
            )

            if (
                content_type
                and "html"
                not in content_type
            ):
                continue

            final_url = normalize_url(
                str(
                    response.url
                )
            )

            if not final_url:
                continue

            # Redirects are allowed only when they remain
            # on the official website or supported social site.
            if not is_allowed_research_url(
                final_url,
                base_url,
            ):
                continue

            visited.add(
                final_url
            )

            # =================================================
            # PARSE PAGE
            # =================================================

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            # -------------------------------------------------
            # JSON-LD
            # -------------------------------------------------

            extract_json_ld(
                soup,
                website_data,
            )

            # -------------------------------------------------
            # HTML / META / CONTACT DATA
            # -------------------------------------------------

            extract_html_data(
                soup,
                final_url,
                website_data,
            )

            # -------------------------------------------------
            # ADDRESS
            # -------------------------------------------------

            extract_addresses(
                soup,
                website_data,
            )

            # -------------------------------------------------
            # SOCIAL BROWSER FALLBACK
            # -------------------------------------------------

            # Public Facebook/Instagram/LinkedIn pages can show contact
            # details in a real browser while omitting them from the raw
            # httpx HTML response. Render only social profiles, and only
            # when address/contact data is still missing.
            if (
                is_social_url(current_url)
                and (
                    not enriched.get("address")
                    or not enriched.get("email")
                    or not enriched.get("phone")
                )
            ):
                rendered = await fetch_rendered_social_page(
                    current_url
                )

                if rendered:
                    rendered_html, rendered_text = rendered

                    rendered_soup = BeautifulSoup(
                        rendered_html,
                        "html.parser",
                    )

                    extract_json_ld(
                        rendered_soup,
                        website_data,
                    )

                    extract_html_data(
                        rendered_soup,
                        current_url,
                        website_data,
                    )

                    extract_addresses(
                        rendered_soup,
                        website_data,
                    )

                    extract_visible_social_text(
                        rendered_text,
                        website_data,
                    )

            # -------------------------------------------------
            # FILL WHATEVER WE HAVE FOUND SO FAR
            # -------------------------------------------------

            merge_research_data(
                enriched,
                website_data,
                base_url,
            )

            # -------------------------------------------------
            # STOP IF EVERYTHING IS FILLED
            # -------------------------------------------------

            if research_complete(
                enriched
            ):
                break

            # -------------------------------------------------
            # DEPTH LIMIT
            # -------------------------------------------------

            if depth >= MAX_RESEARCH_DEPTH:
                continue

            # -------------------------------------------------
            # DISCOVER NEXT RESEARCH LINKS
            # -------------------------------------------------

            new_pages = (
                discover_research_links(
                    soup,
                    final_url,
                    base_url,
                    website_data,
                )
            )

            for page_url in new_pages:

                normalized = normalize_url(
                    page_url
                )

                if not normalized:
                    continue

                if (
                    normalized in visited
                    or any(
                        queued_url
                        == normalized
                        for (
                            queued_url,
                            _,
                        )
                        in queue
                    )
                ):
                    continue

                if not is_allowed_research_url(
                    normalized,
                    base_url,
                ):
                    continue

                queue.append(
                    (
                        normalized,
                        depth + 1,
                    )
                )

    # ========================================================
    # FINAL MERGE
    # ========================================================

    merge_research_data(
        enriched,
        website_data,
        base_url,
    )

    # ========================================================
    # GOOGLE SEARCH FALLBACK FOR STILL-MISSING FIELDS
    # ========================================================

    enriched = await research_missing_fields_with_google(
        enriched
    )

    return enriched
