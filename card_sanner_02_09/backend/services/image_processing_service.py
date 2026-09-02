import cv2
import numpy as np

from typing import Optional

from pyzbar.pyzbar import decode as pyzbar_decode


# ============================================================
# BYTES -> IMAGE
# ============================================================

def bytes_to_image(file_bytes: bytes) -> np.ndarray:
    """
    Convert raw image bytes into an OpenCV image.
    """

    if not file_bytes:
        raise ValueError("Image bytes are empty")

    np_array = np.frombuffer(
        file_bytes,
        dtype=np.uint8,
    )

    image = cv2.imdecode(
        np_array,
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise ValueError(
            "Unable to decode image"
        )

    return image


# ============================================================
# IMAGE -> BYTES
# ============================================================

def image_to_bytes(
    image: np.ndarray,
    extension: str = ".jpg",
) -> bytes:
    """
    Convert an OpenCV image back into image bytes.
    """

    success, encoded = cv2.imencode(
        extension,
        image,
    )

    if not success:
        raise ValueError(
            "Unable to encode processed image"
        )

    return encoded.tobytes()


# ============================================================
# PREPROCESS IMAGE
# ============================================================

def preprocess_image(
    file_bytes: bytes,
    target_width: int = 1600,
) -> bytes:
    """
    Preprocess a business-card image using OpenCV.

    Steps:
    1. Decode image
    2. Resize large images
    3. Improve contrast
    4. Reduce noise
    5. Sharpen the image
    6. Return JPEG bytes

    The returned bytes can be sent to the VLM.
    """

    image = bytes_to_image(
        file_bytes
    )

    # -----------------------------------------
    # 1. Resize
    # -----------------------------------------

    height, width = image.shape[:2]

    if width > target_width:

        scale = (
            target_width
            / float(width)
        )

        new_width = target_width

        new_height = int(
            height * scale
        )

        image = cv2.resize(
            image,
            (
                new_width,
                new_height,
            ),
            interpolation=cv2.INTER_AREA,
        )

    # -----------------------------------------
    # 2. Convert to LAB
    # -----------------------------------------

    lab = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2LAB,
    )

    l_channel, a_channel, b_channel = (
        cv2.split(lab)
    )

    # -----------------------------------------
    # 3. Improve contrast
    # -----------------------------------------

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )

    l_channel = clahe.apply(
        l_channel
    )

    lab = cv2.merge(
        (
            l_channel,
            a_channel,
            b_channel,
        )
    )

    image = cv2.cvtColor(
        lab,
        cv2.COLOR_LAB2BGR,
    )

    # -----------------------------------------
    # 4. Reduce noise
    # -----------------------------------------

    image = cv2.GaussianBlur(
        image,
        (3, 3),
        0,
    )

    # -----------------------------------------
    # 5. Sharpen
    # -----------------------------------------

    kernel = np.array(
        [
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0],
        ],
        dtype=np.float32,
    )

    image = cv2.filter2D(
        image,
        -1,
        kernel,
    )

    # -----------------------------------------
    # 6. Encode as JPEG
    # -----------------------------------------

    return image_to_bytes(
        image,
        extension=".jpg",
    )


# ============================================================
# SINGLE QR CODE
# ============================================================

def detect_qr_code(
    file_bytes: bytes,
) -> Optional[str]:
    """
    Backward-compatible single QR detector.

    Returns the first QR code found.

    For multiple QR codes use:
        detect_qr_codes()
    """

    results = detect_qr_codes(
        file_bytes
    )

    if results:
        return results[0]

    return None


# ============================================================
# MULTIPLE QR CODE DETECTION
# ============================================================

def detect_qr_codes(
    file_bytes: bytes,
) -> list[str]:
    """
    Detect ALL QR codes from a business-card image.

    Detection strategies:

    1. OpenCV Multi QR
    2. OpenCV Single QR
    3. pyzbar / zbar
    4. Original color image
    5. CLAHE
    6. Adaptive threshold
    7. Otsu threshold
    8. Upscaling
    9. Rotation
    10. Sharpening

    Every QR result is collected.

    Duplicate QR values are removed.

    IMPORTANT:
    This function intentionally does NOT return
    immediately after finding a QR code.
    """

    if not file_bytes:
        return []

    # --------------------------------------------------------
    # Decode image
    # --------------------------------------------------------

    image = bytes_to_image(
        file_bytes
    )

    detector = cv2.QRCodeDetector()

    # --------------------------------------------------------
    # Store all unique QR codes
    # --------------------------------------------------------

    found: list[str] = []

    # --------------------------------------------------------
    # Add unique QR
    # --------------------------------------------------------

    def _add(
        value: str | None,
    ):
        """
        Add a QR value if it is valid
        and not already detected.
        """

        if not value:
            return

        if not isinstance(
            value,
            str,
        ):
            return

        cleaned = value.strip()

        if (
            cleaned
            and cleaned not in found
        ):
            found.append(
                cleaned
            )

    # --------------------------------------------------------
    # Try all detectors
    # --------------------------------------------------------

    def _try(
        img: np.ndarray,
    ):
        """
        Run OpenCV and pyzbar
        against one image variant.
        """

        # ====================================================
        # 1. OpenCV Multi QR
        # ====================================================

        try:

            (
                success,
                decoded_info,
                points,
                straight_qrcode,
            ) = detector.detectAndDecodeMulti(
                img
            )

            if (
                success
                and decoded_info
            ):

                for value in decoded_info:

                    _add(value)

        except Exception as exc:

            print(
                "OpenCV multi QR detection failed:",
                exc,
            )

        # ====================================================
        # 2. OpenCV Single QR
        # ====================================================

        try:

            (
                data,
                points,
                straight_qrcode,
            ) = detector.detectAndDecode(
                img
            )

            _add(data)

        except Exception as exc:

            print(
                "OpenCV single QR detection failed:",
                exc,
            )

        # ====================================================
        # 3. pyzbar / zbar
        # ====================================================

        try:

            decoded_objects = (
                pyzbar_decode(img)
            )

            for obj in decoded_objects:

                # Only process QR codes
                if obj.type != "QRCODE":
                    continue

                try:

                    value = (
                        obj.data
                        .decode("utf-8")
                        .strip()
                    )

                except UnicodeDecodeError:

                    continue

                _add(value)

        except Exception as exc:

            print(
                "pyzbar QR detection failed:",
                exc,
            )

    # ========================================================
    # 1. ORIGINAL COLOR IMAGE
    # ========================================================

    _try(image)

    # IMPORTANT:
    #
    # DO NOT:
    #
    # if found:
    #     return found
    #
    # We must continue searching for
    # additional QR codes.
    #

    # ========================================================
    # Convert to grayscale
    # ========================================================

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    # ========================================================
    # 2. STRONG CLAHE
    # ========================================================

    clahe = cv2.createCLAHE(
        clipLimit=4.0,
        tileGridSize=(8, 8),
    )

    enhanced = clahe.apply(
        gray
    )

    _try(enhanced)

    # ========================================================
    # 3. ADAPTIVE THRESHOLD
    # ========================================================

    for block in (
        21,
        31,
        41,
        51,
        71,
    ):

        for c in (
            3,
            5,
            7,
            10,
            15,
        ):

            adaptive = (
                cv2.adaptiveThreshold(
                    gray,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    block,
                    c,
                )
            )

            # Normal threshold
            _try(adaptive)

            # Inverted threshold
            _try(
                cv2.bitwise_not(
                    adaptive
                )
            )

    # ========================================================
    # 4. OTSU THRESHOLD
    # ========================================================

    blurred = cv2.GaussianBlur(
        gray,
        (3, 3),
        0,
    )

    _, otsu = cv2.threshold(
        blurred,
        0,
        255,
        (
            cv2.THRESH_BINARY
            + cv2.THRESH_OTSU
        ),
    )

    _try(otsu)

    _try(
        cv2.bitwise_not(
            otsu
        )
    )

    # ========================================================
    # 5. UPSCALE
    # ========================================================

    for scale in (
        1.5,
        2.0,
        2.5,
        3.0,
    ):

        upscaled = cv2.resize(
            gray,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )

        # Normal upscaled
        _try(upscaled)

        # CLAHE upscaled
        _try(
            clahe.apply(
                upscaled
            )
        )

    # ========================================================
    # 6. ROTATION
    # ========================================================

    height, width = gray.shape[:2]

    center = (
        width // 2,
        height // 2,
    )

    for angle in (
        -12,
        -8,
        -5,
        -3,
        3,
        5,
        8,
        12,
    ):

        matrix = cv2.getRotationMatrix2D(
            center,
            angle,
            1.0,
        )

        rotated = cv2.warpAffine(
            gray,
            matrix,
            (
                width,
                height,
            ),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )

        # Rotated
        _try(rotated)

        # Rotated + CLAHE
        _try(
            clahe.apply(
                rotated
            )
        )

    # ========================================================
    # 7. SHARPEN
    # ========================================================

    kernel = np.array(
        [
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0],
        ],
        dtype=np.float32,
    )

    sharpened = cv2.filter2D(
        gray,
        -1,
        kernel,
    )

    _try(sharpened)

    _try(
        clahe.apply(
            sharpened
        )
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print(
        "========================================"
    )

    print(
        "QR detection complete."
    )

    print(
        f"Found {len(found)} unique QR code(s)."
    )

    for index, value in enumerate(
        found,
        start=1,
    ):

        print(
            f"QR {index}: {value}"
        )

    print(
        "========================================"
    )

    return found


# ============================================================
# RESIZE IMAGE
# ============================================================

def resize_image(
    file_bytes: bytes,
    max_width: int = 1600,
    max_height: int = 1200,
) -> bytes:
    """
    Resize an image while maintaining aspect ratio.
    """

    image = bytes_to_image(
        file_bytes
    )

    height, width = image.shape[:2]

    scale = min(
        max_width / width,
        max_height / height,
        1.0,
    )

    if scale < 1.0:

        new_width = int(
            width * scale
        )

        new_height = int(
            height * scale
        )

        image = cv2.resize(
            image,
            (
                new_width,
                new_height,
            ),
            interpolation=cv2.INTER_AREA,
        )

    return image_to_bytes(
        image,
        extension=".jpg",
    )


# ============================================================
# CROP CARD
# ============================================================

def crop_card(
    file_bytes: bytes,
) -> bytes:
    """
    Attempt to detect the largest rectangular area
    representing the business card.

    If detection fails, returns the original image.
    """

    image = bytes_to_image(
        file_bytes
    )

    original = image.copy()

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    blurred = cv2.GaussianBlur(
        gray,
        (5, 5),
        0,
    )

    edges = cv2.Canny(
        blurred,
        50,
        150,
    )

    contours, _ = cv2.findContours(
        edges,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    image_area = (
        image.shape[0]
        * image.shape[1]
    )

    best_contour = None
    best_area = 0

    for contour in contours:

        area = cv2.contourArea(
            contour
        )

        if area < image_area * 0.10:
            continue

        perimeter = cv2.arcLength(
            contour,
            True,
        )

        approx = cv2.approxPolyDP(
            contour,
            0.02 * perimeter,
            True,
        )

        if (
            len(approx) == 4
            and area > best_area
        ):

            best_area = area
            best_contour = approx

    if best_contour is None:

        return image_to_bytes(
            original
        )

    points = (
        best_contour.reshape(
            4,
            2,
        )
    )

    # --------------------------------------------------------
    # Order points:
    # top-left
    # top-right
    # bottom-right
    # bottom-left
    # --------------------------------------------------------

    rect = np.zeros(
        (4, 2),
        dtype=np.float32,
    )

    sums = points.sum(
        axis=1
    )

    rect[0] = points[
        np.argmin(sums)
    ]

    rect[2] = points[
        np.argmax(sums)
    ]

    differences = np.diff(
        points,
        axis=1,
    )

    rect[1] = points[
        np.argmin(differences)
    ]

    rect[3] = points[
        np.argmax(differences)
    ]

    width_a = np.linalg.norm(
        rect[2] - rect[3]
    )

    width_b = np.linalg.norm(
        rect[1] - rect[0]
    )

    height_a = np.linalg.norm(
        rect[1] - rect[2]
    )

    height_b = np.linalg.norm(
        rect[0] - rect[3]
    )

    max_width = max(
        int(width_a),
        int(width_b),
    )

    max_height = max(
        int(height_a),
        int(height_b),
    )

    if (
        max_width <= 0
        or max_height <= 0
    ):

        return image_to_bytes(
            original
        )

    destination = np.array(
        [
            [0, 0],
            [
                max_width - 1,
                0,
            ],
            [
                max_width - 1,
                max_height - 1,
            ],
            [
                0,
                max_height - 1,
            ],
        ],
        dtype=np.float32,
    )

    matrix = cv2.getPerspectiveTransform(
        rect,
        destination,
    )

    warped = cv2.warpPerspective(
        image,
        matrix,
        (
            max_width,
            max_height,
        ),
    )

    return image_to_bytes(
        warped
    )


# ============================================================
# CROP NORMALIZED REGION
# ============================================================

def crop_normalized_region(
    file_bytes: bytes,
    bbox: list[int],
    padding: float = 0.05,
) -> bytes:
    """
    Crop a region from an image using Gemini's
    normalized bounding-box coordinates.

    Expected format:

    [ymin, xmin, ymax, xmax]

    All coordinates are normalized from 0 to 1000.

    This function is mainly used to crop the
    company logo detected by the VLM.
    """

    # --------------------------------------------------------
    # Validate image
    # --------------------------------------------------------

    if not file_bytes:

        raise ValueError(
            "Image bytes are empty"
        )

    # --------------------------------------------------------
    # Validate bounding box
    # --------------------------------------------------------

    if not isinstance(
        bbox,
        list,
    ):

        raise ValueError(
            "Bounding box must be a list"
        )

    if len(bbox) != 4:

        raise ValueError(
            "Bounding box must contain exactly 4 values"
        )

    # --------------------------------------------------------
    # Decode image
    # --------------------------------------------------------

    image = bytes_to_image(
        file_bytes
    )

    image_height, image_width = (
        image.shape[:2]
    )

    # --------------------------------------------------------
    # Read Gemini coordinates
    # --------------------------------------------------------

    try:

        ymin = int(bbox[0])
        xmin = int(bbox[1])
        ymax = int(bbox[2])
        xmax = int(bbox[3])

    except (
        TypeError,
        ValueError,
    ) as exc:

        raise ValueError(
            "Bounding box coordinates must be integers"
        ) from exc

    # --------------------------------------------------------
    # Clamp normalized values between 0 and 1000
    # --------------------------------------------------------

    ymin = max(
        0,
        min(1000, ymin),
    )

    xmin = max(
        0,
        min(1000, xmin),
    )

    ymax = max(
        0,
        min(1000, ymax),
    )

    xmax = max(
        0,
        min(1000, xmax),
    )

    # --------------------------------------------------------
    # Validate rectangle
    # --------------------------------------------------------

    if ymax <= ymin:

        raise ValueError(
            "Invalid logo bounding box height"
        )

    if xmax <= xmin:

        raise ValueError(
            "Invalid logo bounding box width"
        )

    # --------------------------------------------------------
    # Convert normalized coordinates to pixels
    # --------------------------------------------------------

    y1 = int(
        (ymin / 1000.0)
        * image_height
    )

    x1 = int(
        (xmin / 1000.0)
        * image_width
    )

    y2 = int(
        (ymax / 1000.0)
        * image_height
    )

    x2 = int(
        (xmax / 1000.0)
        * image_width
    )

    # --------------------------------------------------------
    # Add padding around logo
    # --------------------------------------------------------

    crop_width = x2 - x1

    crop_height = y2 - y1

    padding_x = int(
        crop_width * padding
    )

    padding_y = int(
        crop_height * padding
    )

    x1 = max(
        0,
        x1 - padding_x,
    )

    y1 = max(
        0,
        y1 - padding_y,
    )

    x2 = min(
        image_width,
        x2 + padding_x,
    )

    y2 = min(
        image_height,
        y2 + padding_y,
    )

    # --------------------------------------------------------
    # Crop logo
    # --------------------------------------------------------

    cropped = image[
        y1:y2,
        x1:x2,
    ]

    if cropped.size == 0:

        raise ValueError(
            "Logo crop resulted in an empty image"
        )

    # --------------------------------------------------------
    # Return PNG bytes
    # --------------------------------------------------------

    return image_to_bytes(
        cropped,
        extension=".png",
    )


# ============================================================
# CATEGORIZE QR
# ============================================================

def categorize_qr(
    content: str,
) -> dict:
    """
    Categorize a decoded QR code content.
    """

    if not content:

        return {
            "raw": content,
            "type": "other",
            "label": "Other",
            "url": None,
        }

    raw = content.strip()

    lower = raw.lower()

    # ========================================================
    # Instagram
    # ========================================================

    if (
        "instagram.com" in lower
        or lower.startswith(
            "instagram://"
        )
        or (
            lower.startswith("@")
            and len(lower) < 35
        )
    ):

        username = raw

        if "instagram.com/" in lower:

            username = (
                raw
                .split(
                    "instagram.com/"
                )[-1]
                .split("?")[0]
                .strip("/")
            )

        elif lower.startswith("@"):

            username = raw[1:]

        url = (
            f"https://www.instagram.com/"
            f"{username}"
        )

        return {
            "raw": raw,
            "type": "instagram",
            "label": "Instagram",
            "url": url,
        }

    # ========================================================
    # WhatsApp
    # ========================================================

    if (
        "wa.me" in lower
        or "whatsapp" in lower
        or lower.startswith(
            "whatsapp://"
        )
    ):

        return {
            "raw": raw,
            "type": "whatsapp",
            "label": "WhatsApp",
            "url": (
                raw
                if raw.startswith("http")
                else f"https://{raw}"
            ),
        }

    # ========================================================
    # Phone
    # ========================================================

    if (
        lower.startswith("tel:")
        or (
            lower
            .replace("+", "")
            .replace(" ", "")
            .replace("-", "")
            .isdigit()
            and len(
                lower.replace(" ", "")
            ) >= 8
        )
    ):

        phone = (
            raw
            .replace(
                "tel:",
                "",
            )
            .strip()
        )

        return {
            "raw": raw,
            "type": "phone",
            "label": "Phone",
            "url": f"tel:{phone}",
        }

    # ========================================================
    # Email
    # ========================================================

    if (
        lower.startswith("mailto:")
        or (
            "@" in lower
            and "." in lower
        )
    ):

        email = (
            raw
            .replace(
                "mailto:",
                "",
            )
            .strip()
        )

        return {
            "raw": raw,
            "type": "email",
            "label": "Email",
            "url": f"mailto:{email}",
        }

    # ========================================================
    # Location / Maps
    # ========================================================

    if (
        "maps.google" in lower
        or "goo.gl/maps" in lower
        or lower.startswith("geo:")
        or "maps.app.goo.gl" in lower
    ):

        return {
            "raw": raw,
            "type": "location",
            "label": "Location",
            "url": (
                raw
                if raw.startswith("http")
                else f"https://{raw}"
            ),
        }

    # ========================================================
    # Website
    # ========================================================

    if (
        lower.startswith("http://")
        or lower.startswith("https://")
    ):

        return {
            "raw": raw,
            "type": "website",
            "label": "Website",
            "url": raw,
        }

    # ========================================================
    # Fallback
    # ========================================================

    return {
        "raw": raw,
        "type": "other",
        "label": "Other",
        "url": None,
    }