from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
     Depends,
)

from backend.core.auth import get_current_user

from backend.models.card import (
    CardCreate,
    UrlRequest,
)

from backend.services.card_service import (
    create_card,
    get_all_cards,
    delete_card,
)

from backend.services.scanner_service import (
    process_scan,
)

from backend.services.pdf_service import (
    process_pdf,
)

from backend.services.enrichment_service import (
    process_url,
    enrich_business_card,
)


router = APIRouter(
    prefix="/api/cards",
    tags=["Business Cards"],
)


# ============================================================
# SAFE WEBSITE ENRICHMENT
# ============================================================

async def _safe_enrich_card(
    card: dict,
) -> dict:
    """
    Try to enrich missing business-card information
    from the official website.

    If enrichment fails, return the original scanned
    card so normal scanning is never interrupted.
    """

    try:

        enriched_card = await enrich_business_card(
            card
        )

        return enriched_card

    except Exception as e:

        print(
            "ENRICHMENT ERROR:",
            repr(e),
        )

        return card


# ============================================================
# SCAN BUSINESS CARD - FRONT + BACK
# ============================================================

@router.post("/scan")
async def scan_card(
    front_file: UploadFile = File(...),
    back_file: UploadFile | None = File(None),
):
    """
    Scan a business card using front and optional back images.

    Flow:

    1. Read front/back images
    2. Extract visible card information
    3. Detect QR codes
    4. Detect/crop company logo
    5. Upload company logo
    6. Enrich missing information from official website
    """

    try:

        # =====================================================
        # FRONT IMAGE
        # =====================================================

        front_bytes = await front_file.read()

        if not front_bytes:

            raise HTTPException(
                status_code=400,
                detail="Front-side image is empty",
            )

        front_mime_type = (
            front_file.content_type
            or "image/jpeg"
        )

        # =====================================================
        # BACK IMAGE
        # =====================================================

        back_bytes = None
        back_mime_type = "image/jpeg"

        if back_file is not None:

            temp_back_bytes = await back_file.read()

            if temp_back_bytes:

                back_bytes = temp_back_bytes

                back_mime_type = (
                    back_file.content_type
                    or "image/jpeg"
                )

        # =====================================================
        # PROCESS BOTH SIDES
        # =====================================================

        card = process_scan(
            front_bytes=front_bytes,
            back_bytes=back_bytes,
            front_mime_type=front_mime_type,
            back_mime_type=back_mime_type,
        )

        # =====================================================
        # WEBSITE ENRICHMENT
        # =====================================================

        card = await _safe_enrich_card(
            card
        )

        # =====================================================
        # RESPONSE
        # =====================================================

        return {
            "success": True,
            "message": "Business card processed successfully",
            "card": card,
        }

    except HTTPException:
        raise

    except RuntimeError as e:

        print(
            "SCAN ERROR:",
            repr(e),
        )

        error_message = str(e)

        if "Gemini API quota exceeded" in error_message:

            raise HTTPException(
                status_code=503,
                detail=error_message,
            ) from e

        raise HTTPException(
            status_code=500,
            detail=error_message,
        ) from e

    except Exception as e:

        print(
            "SCAN ERROR:",
            repr(e),
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e


# ============================================================
# PDF BUSINESS CARD SCAN - MULTIPLE PDFs
# ============================================================

@router.post("/pdf")
async def process_card_pdf(
    files: list[UploadFile] = File(...),
):
    """
    Process one or multiple business-card PDFs.

    PDF structure:

        Page 1 -> Front
        Page 2 -> Back

    Multiple PDFs are processed independently.

    Example:

        PDF 1 -> Card 1
        PDF 2 -> Card 2
        PDF 3 -> Card 3

    Response:

        {
            "success": true,
            "message": "...",
            "cards": [
                {...},
                {...}
            ]
        }

    The first card is also returned as "card" for
    backward compatibility.
    """

    try:

        # =====================================================
        # VALIDATE FILE LIST
        # =====================================================

        if not files:

            raise HTTPException(
                status_code=400,
                detail="Please upload at least one PDF file",
            )

        extracted_cards: list[dict] = []

        # =====================================================
        # PROCESS EACH PDF
        # =====================================================

        for index, file in enumerate(files):

            print(
                "\n"
                + "=" * 60
            )

            print(
                f"PROCESSING PDF {index + 1}/{len(files)}"
            )

            print(
                f"PDF NAME: {file.filename}"
            )

            print(
                "=" * 60
            )

            # =================================================
            # VALIDATE FILE TYPE
            # =================================================

            filename = (
                file.filename or ""
            ).lower()

            content_type = (
                file.content_type or ""
            ).lower()

            if (
                content_type != "application/pdf"
                and not filename.endswith(".pdf")
            ):

                print(
                    f"Skipping invalid file: {file.filename}"
                )

                continue

            # =================================================
            # READ PDF
            # =================================================

            file_bytes = await file.read()

            if not file_bytes:

                print(
                    f"Skipping empty PDF: {file.filename}"
                )

                continue

            # =================================================
            # CONVERT PDF -> FRONT/BACK IMAGES
            # =================================================

            try:

                pdf_data = process_pdf(
                    file_bytes=file_bytes,
                )

            except Exception as e:

                print(
                    f"PDF PROCESSING ERROR "
                    f"[{file.filename}]:",
                    repr(e),
                )

                continue

            # =================================================
            # GET FRONT/BACK
            # =================================================

            front_bytes = pdf_data.get(
                "front_bytes"
            )

            back_bytes = pdf_data.get(
                "back_bytes"
            )

            front_mime_type = pdf_data.get(
                "front_mime_type",
                "image/jpeg",
            )

            back_mime_type = pdf_data.get(
                "back_mime_type",
                "image/jpeg",
            )

            if not front_bytes:

                print(
                    f"No front page extracted "
                    f"from: {file.filename}"
                )

                continue

            # =================================================
            # RUN NORMAL CARD SCANNER
            # =================================================

            try:

                card = process_scan(
                    front_bytes=front_bytes,
                    back_bytes=back_bytes,
                    front_mime_type=front_mime_type,
                    back_mime_type=back_mime_type,
                )

            except Exception as e:

                print(
                    f"CARD SCAN ERROR "
                    f"[{file.filename}]:",
                    repr(e),
                )

                continue

            # =================================================
            # WEBSITE ENRICHMENT
            # =================================================

            card = await _safe_enrich_card(
                card
            )

            # =================================================
            # ADD PDF INFORMATION
            # =================================================

            card["source_type"] = "pdf"

            card["original_file_url"] = None

            # Keep the original filename so the frontend
            # can identify which PDF generated this card.

            card["_pdf_filename"] = (
                file.filename
            )

            # =================================================
            # ADD CARD TO RESULT
            # =================================================

            extracted_cards.append(
                card
            )

            print(
                f"PDF {index + 1} processed successfully"
            )

            print(
                f"QR CODES: "
                f"{card.get('qr_codes', [])}"
            )

            print(
                f"QR COUNT: "
                f"{len(card.get('qr_codes', []))}"
            )

        # =====================================================
        # NO CARDS EXTRACTED
        # =====================================================

        if not extracted_cards:

            raise HTTPException(
                status_code=400,
                detail="Could not extract any business cards from the uploaded PDFs",
            )

        # =====================================================
        # REMOVE INTERNAL PDF FILENAME
        # =====================================================

        # Keep this field available for frontend debugging /
        # multiple-card identification.
        #
        # It is intentionally not removed here.

        # =====================================================
        # RESPONSE
        # =====================================================

        print(
            "\n"
            + "=" * 60
        )

        print(
            "TOTAL PDFS RECEIVED:",
            len(files),
        )

        print(
            "TOTAL CARDS EXTRACTED:",
            len(extracted_cards),
        )

        print(
            "=" * 60
        )

        return {
            "success": True,
            "message": (
                f"{len(extracted_cards)} "
                f"business card"
                f"{'s' if len(extracted_cards) != 1 else ''} "
                "processed successfully"
            ),

            # New multiple-card response
            "cards": extracted_cards,

            # Backward compatibility:
            # existing frontend can still access first card.
            "card": extracted_cards[0],

            "count": len(extracted_cards),
        }

    except HTTPException:
        raise

    except RuntimeError as e:

        print(
            "PDF SCAN ERROR:",
            repr(e),
        )

        error_message = str(e)

        if "Gemini API quota exceeded" in error_message:

            raise HTTPException(
                status_code=503,
                detail=error_message,
            ) from e

        raise HTTPException(
            status_code=500,
            detail=error_message,
        ) from e

    except Exception as e:

        print(
            "PDF SCAN ERROR:",
            repr(e),
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e


# ============================================================
# URL
# ============================================================

@router.post("/url")
async def process_card_url(
    request: UrlRequest,
):
    """
    Process a company website URL
    and enrich available company information.
    """

    try:

        # =====================================================
        # BASIC URL PROCESSING
        # =====================================================

        card = process_url(
            request.url
        )

        # process_url() currently stores the URL as
        # original_file_url.
        #
        # Website enrichment expects website_url.

        card["website_url"] = (
            request.url
        )

        # =====================================================
        # WEBSITE ENRICHMENT
        # =====================================================

        card = await _safe_enrich_card(
            card
        )

        # =====================================================
        # RESPONSE
        # =====================================================

        return {
            "success": True,
            "message": "URL processed successfully",
            "card": card,
        }

    except Exception as e:

        print(
            "URL ERROR:",
            repr(e),
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        ) from e


# ============================================================
# SAVE CARD
# ============================================================

@router.post("")
async def save_business_card(
    card: CardCreate,
    current_user: dict = Depends(get_current_user),
):
    try:

        # =====================================================
        # DEBUG QR DATA
        # =====================================================

        print(
            "SAVE CARD - QR CODES:",
            card.qr_codes,
        )

        print(
            "SAVE CARD - QR COUNT:",
            len(card.qr_codes or []),
        )

        print(
            "SAVE CARD - QR RAW:",
            card.qr_raw,
        )

        # =====================================================
        # PREPARE DATA
        # =====================================================

        card_data = card.model_dump(
            exclude_none=True
        )

        # =====================================================
        # QR BACKWARD COMPATIBILITY
        # =====================================================

        qr_codes = card_data.get(
            "qr_codes"
        )

        qr_raw = card_data.get(
            "qr_raw"
        )

        # If qr_codes exists, make sure qr_raw also
        # contains the first QR code.

        if qr_codes:

            card_data["qr_codes"] = [
                qr.strip()
                for qr in qr_codes
                if isinstance(qr, str)
                and qr.strip()
            ]

            if card_data["qr_codes"]:

                # Keep first QR in qr_raw for old code.
                if not qr_raw:

                    card_data["qr_raw"] = (
                        card_data["qr_codes"][0]
                    )

        # =====================================================
        # SAVE TO SUPABASE
        # =====================================================

        saved_card = create_card(
        card_data,
        str(current_user["id"]),
    )

        # =====================================================
        # DEBUG SAVED DATA
        # =====================================================

        print(
            "SAVED CARD ID:",
            saved_card.get("id"),
        )

        print(
            "SAVED QR CODES:",
            saved_card.get("qr_codes"),
        )

        print(
            "SAVED QR COUNT:",
            len(
                saved_card.get(
                    "qr_codes"
                )
                or []
            ),
        )

        # =====================================================
        # RESPONSE
        # =====================================================

        return {
            "success": True,
            "message": "Business card saved successfully",
            "card": saved_card,
        }

    except Exception as e:

        print(
            "SAVE CARD ERROR:",
            repr(e),
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# GET ALL CARDS
# ============================================================

@router.get("")
async def get_business_cards(
    current_user: dict = Depends(get_current_user),
):

    try:

        cards = get_all_cards(
            str(current_user["id"])
        )

        return {
            "success": True,
            "message": "Business cards fetched successfully",
            "data": cards,
        }

    except Exception as e:

        print(
            "GET CARDS ERROR:",
            repr(e),
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# DELETE CARD
# ============================================================

@router.delete("/{card_id}")
async def remove_business_card(
    card_id: str,
    current_user: dict = Depends(get_current_user),
):

    try:

        deleted = delete_card(
        card_id,
        str(current_user["id"]),
    )

        if not deleted:

            raise HTTPException(
                status_code=404,
                detail="Business card not found",
            )

        return {
            "success": True,
            "message": "Business card deleted successfully",
            "data": None,
        }

    except HTTPException:
        raise

    except Exception as e:

        print(
            "DELETE CARD ERROR:",
            repr(e),
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )