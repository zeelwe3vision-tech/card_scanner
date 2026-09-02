from uuid import uuid4

from supabase import create_client, Client

from backend.core.config import settings


# ============================================================
# NORMAL SUPABASE CLIENT
# ============================================================

# Used by the normal application/database operations.

supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_key,
)


# ============================================================
# SERVER-ONLY ADMIN CLIENT
# ============================================================

# Used only for privileged backend operations
# such as uploading files to Supabase Storage.

supabase_admin: Client = create_client(
    settings.supabase_url,
    settings.supabase_secret_key,
)


# ============================================================
# STORAGE CONFIGURATION
# ============================================================

CARD_LOGOS_BUCKET = "card-logos"


# ============================================================
# UPLOAD COMPANY LOGO
# ============================================================

def upload_company_logo(
    logo_bytes: bytes,
) -> str | None:
    """
    Upload a cropped company logo to Supabase Storage
    and return its public URL.
    """

    if not logo_bytes:
        return None

    # --------------------------------------------------------
    # Generate unique filename
    # --------------------------------------------------------

    file_name = f"{uuid4()}.png"

    file_path = f"logos/{file_name}"

    # --------------------------------------------------------
    # Upload using server-side secret/admin client
    # --------------------------------------------------------

    supabase_admin.storage.from_(
        CARD_LOGOS_BUCKET
    ).upload(
        path=file_path,
        file=logo_bytes,
        file_options={
            "content-type": "image/png",
        },
    )

    # --------------------------------------------------------
    # Get public URL
    # --------------------------------------------------------

    public_url = (
        supabase_admin.storage
        .from_(CARD_LOGOS_BUCKET)
        .get_public_url(file_path)
    )

    if not public_url:
        return None

    return str(public_url)