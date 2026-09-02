from typing import Any, Optional

from backend.services.image_processing_service import (
    preprocess_image,
    detect_qr_codes,
    crop_card,
    crop_normalized_region,
    categorize_qr,
)

from backend.services.vlm_service import (
    extract_business_card,
)

from backend.core.supabase import (
    upload_company_logo,
)


# ============================================================
# QR CODE HELPERS
# ============================================================

def _normalize_qr_value(
    value: Any,
) -> Optional[str]:
    """
    Convert a QR value into a clean string.

    Returns None for empty/invalid values.
    """

    if value is None:
        return None

    if not isinstance(value, str):
        value = str(value)

    value = value.strip()

    if not value:
        return None

    return value


def _append_unique_qr(
    qr_list: list[str],
    value: Any,
) -> None:
    """
    Add one QR value to the list only if it is
    non-empty and not already present.
    """

    normalized = _normalize_qr_value(
        value
    )

    if (
        normalized
        and normalized not in qr_list
    ):
        qr_list.append(
            normalized
        )


def _extract_qr_values(
    qr_data: Any,
) -> list[str]:
    """
    Convert different possible QR detector outputs
    into a clean list of strings.

    Supported examples:

        ["https://example.com"]

    or:

        [
            {"data": "https://example.com"},
            {"data": "https://instagram.com/example"}
        ]

    or:

        [
            {"raw": "https://example.com"}
        ]
    """

    results: list[str] = []

    if not qr_data:
        return results

    # --------------------------------------------------------
    # Single string
    # --------------------------------------------------------

    if isinstance(
        qr_data,
        str,
    ):

        _append_unique_qr(
            results,
            qr_data,
        )

        return results

    # --------------------------------------------------------
    # List / tuple
    # --------------------------------------------------------

    if isinstance(
        qr_data,
        (list, tuple),
    ):

        for item in qr_data:

            if isinstance(
                item,
                str,
            ):

                _append_unique_qr(
                    results,
                    item,
                )

            elif isinstance(
                item,
                dict,
            ):

                possible_values = [
                    item.get("data"),
                    item.get("raw"),
                    item.get("url"),
                    item.get("content"),
                ]

                for value in possible_values:

                    if value:

                        _append_unique_qr(
                            results,
                            value,
                        )

                        break

        return results

    # --------------------------------------------------------
    # Dictionary
    # --------------------------------------------------------

    if isinstance(
        qr_data,
        dict,
    ):

        possible_values = [
            qr_data.get("data"),
            qr_data.get("raw"),
            qr_data.get("url"),
            qr_data.get("content"),
        ]

        for value in possible_values:

            if value:

                _append_unique_qr(
                    results,
                    value,
                )

                break

    return results


# ============================================================
# SAFE IMAGE EXTRACTION
# ============================================================

def _safe_extract(
    image_bytes: bytes,
    mime_type: str,
) -> dict[str, Any]:
    """
    Extract business-card information from one image.

    QR detection uses multiple image representations:

    1. Cropped card
    2. Original image

    Results from both are merged and deduplicated.

    Gemini QR extraction is then added as an additional
    source of QR information.
    """

    if not image_bytes:

        return {}

    # ========================================================
    # 1. CROP CARD
    # ========================================================

    try:

        card_bytes = crop_card(
            file_bytes=image_bytes
        )

    except Exception as exc:

        print(
            "Card crop failed, using original image:",
            exc,
        )

        card_bytes = image_bytes

    # ========================================================
    # 2. QR DETECTION
    # ========================================================
    #
    # IMPORTANT:
    #
    # We DO NOT stop after finding QR codes in the
    # cropped image.
    #
    # We also scan the original image because a second
    # QR code may exist outside the crop.
    # ========================================================

    all_raw_qrs: list[str] = []

    # --------------------------------------------------------
    # QR detection on cropped card
    # --------------------------------------------------------

    try:

        cropped_qrs = detect_qr_codes(
            card_bytes
        )

        cropped_qr_values = _extract_qr_values(
            cropped_qrs
        )

        for value in cropped_qr_values:

            _append_unique_qr(
                all_raw_qrs,
                value,
            )

    except Exception as exc:

        print(
            "QR detection on cropped image failed:",
            exc,
        )

    # --------------------------------------------------------
    # QR detection on original image
    # --------------------------------------------------------

    try:

        original_qrs = detect_qr_codes(
            image_bytes
        )

        original_qr_values = _extract_qr_values(
            original_qrs
        )

        for value in original_qr_values:

            _append_unique_qr(
                all_raw_qrs,
                value,
            )

    except Exception as exc:

        print(
            "QR detection on original image failed:",
            exc,
        )

    # ========================================================
    # DEBUG QR RESULTS
    # ========================================================

    print(
        "QR CODES DETECTED BY IMAGE SCANNER:",
        all_raw_qrs,
    )

    print(
        "IMAGE QR COUNT:",
        len(all_raw_qrs),
    )

    # ========================================================
    # 3. GEMINI VLM
    # ========================================================

    try:

        extracted = extract_business_card(
            file_bytes=card_bytes,
            mime_type="image/jpeg",
        )

    except Exception as exc:

        print(
            "VLM extraction failed:",
            exc,
        )

        raise

    if not isinstance(
        extracted,
        dict,
    ):

        extracted = {}

    # ========================================================
    # 4. LOGO
    # ========================================================

    logo_bytes = None

    logo_bbox = extracted.get(
        "logo_bbox"
    )

    if logo_bbox:

        try:

            logo_bytes = crop_normalized_region(
                file_bytes=card_bytes,
                bbox=logo_bbox,
            )

        except Exception as exc:

            print(
                "Logo crop failed:",
                exc,
            )

    extracted["_company_logo_bytes"] = (
        logo_bytes
    )

    # ========================================================
    # 5. GEMINI QR EXTRACTION
    # ========================================================
    #
    # Gemini may return:
    #
    # qr_content
    #
    # or, depending on the VLM implementation:
    #
    # qr_codes
    #
    # or:
    #
    # qr_details
    #
    # We collect all possible values.
    # ========================================================

    # --------------------------------------------------------
    # Legacy Gemini qr_content
    # --------------------------------------------------------

    gemini_qr_content = extracted.get(
        "qr_content"
    )

    gemini_qr_values = _extract_qr_values(
        gemini_qr_content
    )

    for value in gemini_qr_values:

        _append_unique_qr(
            all_raw_qrs,
            value,
        )

    # --------------------------------------------------------
    # Gemini qr_codes
    # --------------------------------------------------------

    gemini_qr_codes = extracted.get(
        "qr_codes"
    )

    gemini_qr_code_values = _extract_qr_values(
        gemini_qr_codes
    )

    for value in gemini_qr_code_values:

        _append_unique_qr(
            all_raw_qrs,
            value,
        )

    # --------------------------------------------------------
    # Gemini qr_details
    # --------------------------------------------------------

    gemini_qr_details = extracted.get(
        "qr_details"
    )

    if isinstance(
        gemini_qr_details,
        list,
    ):

        for detail in gemini_qr_details:

            if not isinstance(
                detail,
                dict,
            ):

                continue

            possible_values = [
                detail.get("raw"),
                detail.get("url"),
            ]

            for value in possible_values:

                if value:

                    _append_unique_qr(
                        all_raw_qrs,
                        value,
                    )

                    break

    # ========================================================
    # FINAL QR DEBUG
    # ========================================================

    print(
        "FINAL QR CODES FROM IMAGE + GEMINI:",
        all_raw_qrs,
    )

    print(
        "FINAL QR COUNT:",
        len(all_raw_qrs),
    )

    # ========================================================
    # 6. CATEGORIZE EVERY QR
    # ========================================================

    qr_details: list[dict[str, Any]] = []

    for qr in all_raw_qrs:

        try:

            detail = categorize_qr(
                qr
            )

            if isinstance(
                detail,
                dict,
            ):

                qr_details.append(
                    detail
                )

        except Exception as exc:

            print(
                "QR categorization failed:",
                qr,
                exc,
            )

            # Keep the raw QR even if categorization
            # fails.

            qr_details.append(
                {
                    "raw": qr,
                    "type": "other",
                    "label": "QR Code",
                    "url": qr,
                }
            )

    # ========================================================
    # 7. STORE FINAL QR DATA
    # ========================================================

    if qr_details:

        extracted["qr_raw"] = (
            qr_details[0].get(
                "raw"
            )
        )

        extracted["qr_codes"] = [
            detail.get("raw")
            for detail in qr_details
            if detail.get("raw")
        ]

        extracted["qr_details"] = (
            qr_details
        )

    else:

        extracted["qr_raw"] = None

        extracted["qr_codes"] = []

        extracted["qr_details"] = []

    # ========================================================
    # REMOVE TEMPORARY / LEGACY QR FIELD
    # ========================================================

    extracted.pop(
        "qr_content",
        None,
    )

    return extracted


# ============================================================
# MERGE FRONT + BACK
# ============================================================

def _merge_card_data(
    front_data: dict[str, Any],
    back_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge information extracted from both sides.

    Front-side information gets priority for normal
    business-card fields.

    QR codes from BOTH sides are always combined.

    QR details from BOTH sides are always combined.

    Duplicate QR codes are removed.
    """

    fields = [
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
    ]

    merged: dict[str, Any] = {}

    # ========================================================
    # NORMAL FIELDS
    # ========================================================

    for field in fields:

        front_value = front_data.get(
            field
        )

        back_value = back_data.get(
            field
        )

        if front_value not in (
            None,
            "",
        ):

            merged[field] = (
                front_value
            )

        elif back_value not in (
            None,
            "",
        ):

            merged[field] = (
                back_value
            )

        else:

            merged[field] = None

    # ========================================================
    # QR CODES FROM FRONT + BACK
    # ========================================================

    front_qr_codes = _extract_qr_values(
        front_data.get(
            "qr_codes",
            [],
        )
    )

    back_qr_codes = _extract_qr_values(
        back_data.get(
            "qr_codes",
            [],
        )
    )

    qr_codes: list[str] = []

    # --------------------------------------------------------
    # Front QR codes
    # --------------------------------------------------------

    for value in front_qr_codes:

        _append_unique_qr(
            qr_codes,
            value,
        )

    # --------------------------------------------------------
    # Back QR codes
    # --------------------------------------------------------

    for value in back_qr_codes:

        _append_unique_qr(
            qr_codes,
            value,
        )

    # ========================================================
    # QR DETAILS FROM FRONT + BACK
    # ========================================================

    merged_qr_details: list[dict[str, Any]] = []

    front_qr_details = front_data.get(
        "qr_details",
        [],
    )

    back_qr_details = back_data.get(
        "qr_details",
        [],
    )

    # --------------------------------------------------------
    # Add front details
    # --------------------------------------------------------

    if isinstance(
        front_qr_details,
        list,
    ):

        for detail in front_qr_details:

            if not isinstance(
                detail,
                dict,
            ):

                continue

            raw = _normalize_qr_value(
                detail.get("raw")
            )

            if not raw:
                continue

            already_exists = any(
                item.get("raw") == raw
                for item in merged_qr_details
            )

            if not already_exists:

                merged_qr_details.append(
                    detail
                )

    # --------------------------------------------------------
    # Add back details
    # --------------------------------------------------------

    if isinstance(
        back_qr_details,
        list,
    ):

        for detail in back_qr_details:

            if not isinstance(
                detail,
                dict,
            ):

                continue

            raw = _normalize_qr_value(
                detail.get("raw")
            )

            if not raw:
                continue

            already_exists = any(
                item.get("raw") == raw
                for item in merged_qr_details
            )

            if not already_exists:

                merged_qr_details.append(
                    detail
                )

    # ========================================================
    # MAKE SURE EVERY QR CODE HAS QR DETAILS
    # ========================================================
    #
    # This handles a situation where qr_codes contains
    # a value but qr_details is missing that value.
    # ========================================================

    detail_raw_values = {
        detail.get("raw")
        for detail in merged_qr_details
        if detail.get("raw")
    }

    for qr in qr_codes:

        if qr not in detail_raw_values:

            try:

                detail = categorize_qr(
                    qr
                )

            except Exception as exc:

                print(
                    "QR categorization during merge failed:",
                    qr,
                    exc,
                )

                detail = {
                    "raw": qr,
                    "type": "other",
                    "label": "QR Code",
                    "url": qr,
                }

            merged_qr_details.append(
                detail
            )

    # ========================================================
    # FINAL QR ARRAY
    # ========================================================

    # Make sure qr_codes also includes anything that
    # appeared inside qr_details.

    for detail in merged_qr_details:

        raw = detail.get(
            "raw"
        )

        _append_unique_qr(
            qr_codes,
            raw,
        )

    merged["qr_codes"] = qr_codes

    merged["qr_details"] = (
        merged_qr_details
    )

    # ========================================================
    # LEGACY SINGLE QR FIELD
    # ========================================================

    if qr_codes:

        merged["qr_raw"] = (
            qr_codes[0]
        )

    else:

        merged["qr_raw"] = None

    # ========================================================
    # DEBUG MERGED QR DATA
    # ========================================================

    print(
        "MERGED QR CODES:",
        merged["qr_codes"],
    )

    print(
        "MERGED QR COUNT:",
        len(
            merged["qr_codes"]
        ),
    )

    print(
        "MERGED QR DETAILS:",
        merged["qr_details"],
    )

    # ========================================================
    # COMPANY LOGO
    # ========================================================

    front_logo_bytes = front_data.get(
        "_company_logo_bytes"
    )

    back_logo_bytes = back_data.get(
        "_company_logo_bytes"
    )

    # Prefer front-side logo.
    # If not available, use back-side logo.

    if front_logo_bytes:

        merged["_company_logo_bytes"] = (
            front_logo_bytes
        )

    elif back_logo_bytes:

        merged["_company_logo_bytes"] = (
            back_logo_bytes
        )

    else:

        merged["_company_logo_bytes"] = None

    return merged


# ============================================================
# MAIN SCAN FUNCTION
# ============================================================

def process_scan(
    front_bytes: bytes,
    back_bytes: Optional[bytes] = None,
    front_mime_type: str = "image/jpeg",
    back_mime_type: str = "image/jpeg",
) -> dict[str, Any]:
    """
    Process the front and optional back side
    of a business card.
    """

    # ========================================================
    # VALIDATE FRONT IMAGE
    # ========================================================

    if not front_bytes:

        raise ValueError(
            "Front-side business card image is required"
        )

    # ========================================================
    # FRONT SIDE
    # ========================================================

    front_data = _safe_extract(
        image_bytes=front_bytes,
        mime_type=front_mime_type,
    )

    # ========================================================
    # BACK SIDE
    # ========================================================

    back_data: dict[str, Any] = {}

    if back_bytes:

        back_data = _safe_extract(
            image_bytes=back_bytes,
            mime_type=back_mime_type,
        )

    # ========================================================
    # MERGE FRONT + BACK
    # ========================================================

    merged_data = _merge_card_data(
        front_data=front_data,
        back_data=back_data,
    )

    # ========================================================
    # GET CROPPED LOGO BYTES
    # ========================================================

    logo_bytes = merged_data.pop(
        "_company_logo_bytes",
        None,
    )

    # ========================================================
    # UPLOAD LOGO TO SUPABASE STORAGE
    # ========================================================

    company_logo_url: str | None = None

    if logo_bytes:

        try:

            company_logo_url = (
                upload_company_logo(
                    logo_bytes=logo_bytes,
                )
            )

        except Exception as exc:

            # Logo failure should NOT prevent
            # the business card from being scanned.

            print(
                "Company logo upload failed:",
                exc,
            )

            company_logo_url = None

    else:

        print(
            "No logo available for upload"
        )

    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    return {
        **merged_data,

        "company_logo": company_logo_url,

        "front_image_url": None,

        "back_image_url": None,

        "source_type": "scan",

        "original_file_url": None,
    }