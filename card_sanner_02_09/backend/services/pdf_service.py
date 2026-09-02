import logging
from typing import Any

import pymupdf


logger = logging.getLogger(__name__)


def pdf_to_images(
    file_bytes: bytes,
    dpi: int = 200,
) -> list[bytes]:
    """
    Convert PDF pages into JPEG images.

    Page 1 = front side
    Page 2 = back side
    """

    if not file_bytes:
        raise ValueError("Empty PDF file")

    document = None

    try:
        document = pymupdf.open(
            stream=file_bytes,
            filetype="pdf",
        )

        if document.page_count == 0:
            raise ValueError("PDF contains no pages")

        images: list[bytes] = []

        scale = dpi / 72

        matrix = pymupdf.Matrix(
            scale,
            scale,
        )

        # We only need the first two pages
        # because they represent front + back.
        page_count = min(
            document.page_count,
            2,
        )

        for page_number in range(page_count):

            page = document.load_page(
                page_number
            )

            pixmap = page.get_pixmap(
                matrix=matrix,
                alpha=False,
            )

            image_bytes = pixmap.tobytes(
                "jpeg"
            )

            images.append(
                image_bytes
            )

            logger.info(
                "Converted PDF page %s/%s to JPEG",
                page_number + 1,
                page_count,
            )

        return images

    except Exception as exc:

        logger.exception(
            "PDF to image conversion failed"
        )

        raise RuntimeError(
            f"Could not convert PDF to images: {exc}"
        ) from exc

    finally:

        if document is not None:
            document.close()


def process_pdf(
    file_bytes: bytes,
) -> dict[str, Any]:
    """
    Convert a business-card PDF into
    front and back image bytes.

    Page 1 -> front
    Page 2 -> back
    """

    images = pdf_to_images(
        file_bytes=file_bytes,
    )

    if not images:
        raise ValueError(
            "No pages found in PDF"
        )

    front_bytes = images[0]

    back_bytes = (
        images[1]
        if len(images) > 1
        else None
    )

    return {
        "front_bytes": front_bytes,

        "back_bytes": back_bytes,

        "front_mime_type": "image/jpeg",

        "back_mime_type": (
            "image/jpeg"
            if back_bytes
            else None
        ),

        "page_count": len(images),

        "source_type": "pdf",
    }