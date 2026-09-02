import json
import logging
from typing import Any

from google import genai
from google.genai import types

from backend.core.config import settings


logger = logging.getLogger(__name__)


# ============================================================
# VLM PROMPT
# ============================================================

VLM_PROMPT = """
You are a business-card information extraction system.

Analyze the provided business-card image and extract only information
that is actually visible or clearly readable.

Do NOT invent, guess, or hallucinate missing information.

Also inspect the ENTIRE business-card image for the company or brand logo.

The logo may appear ANYWHERE in the image.

Return ONLY valid JSON using exactly this structure:

{
    "owner_name": null,
    "designation": null,
    "company_name": null,
    "address": null,
    "email": null,
    "phone": null,
    "gst_number": null,
    "website_url": null,
    "instagram_url": null,
    "facebook_url": null,
    "linkedin_url": null,
    "logo_bbox": null
}


LOGO DETECTION RULES:

1. Search the ENTIRE image for the company or brand logo.

2. Do NOT assume the logo is located in a specific place.

3. The logo may appear:
   - top-left
   - top-center
   - top-right
   - center-left
   - center
   - center-right
   - bottom-left
   - bottom-center
   - bottom-right
   - beside the company name
   - beside the owner name
   - between other elements

4. Examine the complete image before deciding whether a logo exists.

5.A company logo may be:
- a graphical company symbol
- a brand icon
- stylized company initials
- a stylized company wordmark
- a symbol combined with the company name
- the company name itself when it is visually styled as the primary brand mark

IMPORTANT:
If there is no separate graphical symbol, but the company name is prominently
styled, decorated, uniquely typeset, or presented as the main brand identity,
treat that wordmark as the company logo and return its bounding box.

For example, if "DK DESIGN" itself is presented as the main visual brand mark,
return the bounding box around that styled DK DESIGN wordmark.

6. Do NOT identify these as the company logo:
   - QR codes
   - phone icons
   - email icons
   - location icons
   - website icons
   - Instagram icons
   - Facebook icons
   - LinkedIn icons
   - decorative shapes
   - decorative lines
   - background graphics
   - profile photos
   - unrelated images

7. If multiple graphical elements exist, choose the element that most
   clearly represents the company identified by company_name.

8. Do NOT choose something merely because it is large or colorful.

9. If a clear company logo is visible, return its bounding box using:

   "logo_bbox": [ymin, xmin, ymax, xmax]

10. Bounding-box coordinates must be normalized integers from 0 to 1000.

11. Coordinate meaning:
    - ymin = top edge of the logo
    - xmin = left edge of the logo
    - ymax = bottom edge of the logo
    - xmax = right edge of the logo

12. The bounding box must tightly contain the complete logo.

13. If there is no clearly identifiable company logo, return:

    "logo_bbox": null

14. Never guess a logo location.


GENERAL EXTRACTION RULES:

1. If a field is not visible, return null.
2. Preserve names exactly as written on the card.
3. Preserve designation/job title exactly as written.
4. Preserve phone numbers accurately.
5. Preserve email addresses accurately.
6. Preserve website URLs accurately.
7. Preserve GST numbers accurately if visible.
8. Preserve social media URLs accurately if visible.
9. Do not create information that is not present.
10. Do not add explanations.
11. Return JSON only.
"""


# ============================================================
# EXPECTED FIELDS
# ============================================================

EXPECTED_FIELDS = {
    "owner_name",
    "designation",
    "company_name",
    "address",
    "email",
    "phone",
    "gst_number",
    "website_url",
    "instagram_url",
    "facebook_url",
    "linkedin_url",
    "logo_bbox",
    "qr_content",
}
# ============================================================
# CLEAN LOGO BOUNDING BOX
# ============================================================

def _clean_logo_bbox(
    bbox: Any,
) -> list[int] | None:
    """
    Validate Gemini's normalized logo bounding box.

    Expected format:

    [ymin, xmin, ymax, xmax]

    Coordinate range:
    0 to 1000
    """

    # --------------------------------------------------------
    # Must be a list
    # --------------------------------------------------------

    if not isinstance(bbox, list):
        return None

    # --------------------------------------------------------
    # Must contain exactly 4 values
    # --------------------------------------------------------

    if len(bbox) != 4:
        return None

    # --------------------------------------------------------
    # Convert values to integers
    # --------------------------------------------------------

    try:
        ymin = int(bbox[0])
        xmin = int(bbox[1])
        ymax = int(bbox[2])
        xmax = int(bbox[3])

    except (TypeError, ValueError):
        return None

    # --------------------------------------------------------
    # Coordinates must be between 0 and 1000
    # --------------------------------------------------------

    values = [
        ymin,
        xmin,
        ymax,
        xmax,
    ]

    if any(
        value < 0 or value > 1000
        for value in values
    ):
        return None

    # --------------------------------------------------------
    # Validate rectangle
    # --------------------------------------------------------

    if ymax <= ymin:
        return None

    if xmax <= xmin:
        return None

    # --------------------------------------------------------
    # Avoid extremely tiny false detections
    # --------------------------------------------------------

    box_height = ymax - ymin
    box_width = xmax - xmin

    if box_width < 20 or box_height < 20:
        return None

    # --------------------------------------------------------
    # Valid logo bounding box
    # --------------------------------------------------------

    return [
        ymin,
        xmin,
        ymax,
        xmax,
    ]


# ============================================================
# CLEAN GEMINI RESPONSE
# ============================================================

def _clean_vlm_response(
    text: str,
) -> dict[str, Any]:
    """
    Convert Gemini's response into a clean Python dictionary.
    """

    # --------------------------------------------------------
    # Empty response check
    # --------------------------------------------------------

    if not text:
        raise ValueError(
            "Gemini returned an empty response"
        )

    text = text.strip()

    # --------------------------------------------------------
    # Remove markdown code fences if Gemini adds them
    # --------------------------------------------------------

    if text.startswith("```"):

        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:
        data = json.loads(text)

    except json.JSONDecodeError:

        # Sometimes Gemini may wrap JSON
        # inside some additional text.

        start = text.find("{")
        end = text.rfind("}")

        if (
            start == -1
            or end == -1
            or end <= start
        ):

            logger.error(
                "Gemini returned invalid JSON: %s",
                text,
            )

            raise ValueError(
                "Gemini returned invalid JSON"
            )

        json_text = text[
            start:end + 1
        ]

        try:
            data = json.loads(
                json_text
            )

        except json.JSONDecodeError as exc:

            logger.error(
                "Could not parse Gemini JSON: %s",
                text,
            )

            raise ValueError(
                "Gemini returned invalid JSON"
            ) from exc

    # --------------------------------------------------------
    # Response must be a JSON object
    # --------------------------------------------------------

    if not isinstance(data, dict):

        raise ValueError(
            "Gemini response must be a JSON object"
        )

    # --------------------------------------------------------
    # Keep only expected fields
    # --------------------------------------------------------

    cleaned = {
        field: data.get(field)
        for field in EXPECTED_FIELDS
    }

    # ========================================================
    # VALIDATE LOGO BOUNDING BOX
    # ========================================================

    logo_bbox = _clean_logo_bbox(
        data.get("logo_bbox")
    )

    cleaned["logo_bbox"] = logo_bbox

    return cleaned


# ============================================================
# GENERATE GEMINI RESPONSE
# ============================================================

def _generate_vlm_response(
    file_bytes: bytes,
    mime_type: str,
) -> str:
    """
    Send the business-card image to Gemini.
    """

    # --------------------------------------------------------
    # API key validation
    # --------------------------------------------------------

    if not settings.gemini_api_key:

        raise RuntimeError(
            "GEMINI_API_KEY is not configured"
        )

    # --------------------------------------------------------
    # Image validation
    # --------------------------------------------------------

    if not file_bytes:

        raise ValueError(
            "Image data is empty"
        )

    logger.info(
        "Sending business card to Gemini VLM "
        "(model=%s)",
        settings.gemini_vlm_model,
    )

    try:

        # ----------------------------------------------------
        # Gemini client
        # ----------------------------------------------------

        client = genai.Client(
            api_key=settings.gemini_api_key
        )

        # ----------------------------------------------------
        # Send image + prompt
        # ----------------------------------------------------

        response = client.models.generate_content(
            model=settings.gemini_vlm_model,

            contents=[
                types.Part.from_bytes(
                    data=file_bytes,
                    mime_type=mime_type,
                ),

                VLM_PROMPT,
            ],

            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )

        # ----------------------------------------------------
        # Read Gemini response
        # ----------------------------------------------------

        response_text = response.text

        if not response_text:

            raise RuntimeError(
                "Gemini returned an empty response"
            )

        logger.info(
            "Gemini VLM response received successfully"
        )

        logger.debug(
            "Gemini raw response: %s",
            response_text,
        )

        return response_text.strip()

    except Exception as exc:

        logger.exception(
            "Gemini VLM request failed"
        )

        raise RuntimeError(
            f"Gemini VLM request failed: {exc}"
        ) from exc


# ============================================================
# EXTRACT BUSINESS CARD
# ============================================================

def extract_business_card(
    file_bytes: bytes,
    mime_type: str,
) -> dict[str, Any]:
    """
    Extract business-card information
    and company-logo position using Gemini VLM.
    """

    # --------------------------------------------------------
    # Image validation
    # --------------------------------------------------------

    if not file_bytes:

        raise ValueError(
            "Empty image file"
        )

    # --------------------------------------------------------
    # MIME type validation
    # --------------------------------------------------------

    if not mime_type.startswith(
        "image/"
    ):

        raise ValueError(
            f"Unsupported MIME type: {mime_type}"
        )

    # --------------------------------------------------------
    # Gemini extraction
    # --------------------------------------------------------

    response_text = _generate_vlm_response(
        file_bytes=file_bytes,
        mime_type=mime_type,
    )

    # --------------------------------------------------------
    # Clean and validate response
    # --------------------------------------------------------

    return _clean_vlm_response(
        response_text
    )

#QR code detection
VLM_PROMPT = """
You are a business-card information extraction system.

Analyze the provided business-card image and extract only information
that is actually visible or clearly readable.

Do NOT invent, guess, or hallucinate missing information.

Also inspect the ENTIRE business-card image for the company or brand logo
and any QR codes.

Return ONLY valid JSON using exactly this structure:

{
    "owner_name": null,
    "designation": null,
    "company_name": null,
    "address": null,
    "email": null,
    "phone": null,
    "gst_number": null,
    "website_url": null,
    "instagram_url": null,
    "facebook_url": null,
    "linkedin_url": null,
    "logo_bbox": null,
    "qr_content": null
}


LOGO DETECTION RULES:

1. Search the ENTIRE image for the company or brand logo.
2. Do NOT assume the logo is located in a specific place.
3. The logo may appear anywhere on the card.
4. A company logo may be a graphical symbol, brand icon, stylized initials,
   or a styled company wordmark.
5. Do NOT identify QR codes, icons, decorative shapes, or profile photos as the logo.
6. If a clear company logo is visible, return its bounding box as:
   "logo_bbox": [ymin, xmin, ymax, xmax]
   (normalized integers from 0 to 1000)
7. If no clear logo exists, return "logo_bbox": null.

QR CODE RULES (VERY IMPORTANT):

1. Carefully examine the entire business card image for any QR codes.
2. Business cards very often contain Instagram QR codes (especially on the back side).
3. Instagram QR codes do **not** always have the Instagram logo in the center.
   Some look like normal black-and-white QR codes.
4. You must try hard to read every QR code you see.
5. Typical Instagram QR content looks like:
   - https://www.instagram.com/username
   - https://instagram.com/username
   - or any link that opens an Instagram profile
6. Also read other common QR contents such as:
   - Website URLs
   - WhatsApp links (wa.me / api.whatsapp.com)
   - Phone numbers
   - Email addresses
7. Return the decoded content in "qr_content".
8. If multiple QR codes exist, prefer the Instagram link if one is present.
9. Never invent or guess the content. Only return what you can actually read.
10. If you can see a QR code but cannot reliably decode it, return null.
11. If no QR code is present, return "qr_content": null.


GENERAL EXTRACTION RULES:

1. If a field is not visible, return null.
2. Preserve names, phone numbers, emails, websites exactly as written.
3. Do not create information that is not present.
4. Return JSON only.
"""