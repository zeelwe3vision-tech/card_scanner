from datetime import datetime, timedelta, timezone
from backend.core.supabase import supabase


TABLE_NAME = "business_cards"


# =====================================================
# QR CODE NORMALIZATION
# =====================================================

def _normalize_qr_codes(
    qr_codes,
) -> list[str]:
    """
    Normalize all QR codes before saving.

    Rules:
    - None -> []
    - Ignore empty values
    - Convert values to strings
    - Remove duplicate QR codes
    - Preserve original order
    """

    if not qr_codes:
        return []

    normalized: list[str] = []

    for qr in qr_codes:

        if qr is None:
            continue

        value = str(qr).strip()

        if not value:
            continue

        if value not in normalized:
            normalized.append(value)

    return normalized


# =====================================================
# CREATE BUSINESS CARD
# =====================================================

def create_card(
    card_data: dict,
    user_id: str,
):
    """
    Save a business card for one specific user.
    """

    # =================================================
    # COPY INPUT
    # =================================================

    data = dict(card_data)

    # =================================================
    # ATTACH CARD TO CURRENT USER
    # =================================================

    data["user_id"] = user_id

    # =================================================
    # CARD RETENTION
    # =================================================

    retention_response = (
        supabase
        .table("login")
        .select("card_retention_days")
        .eq("id", user_id)
        .execute()
    )

    retention_days = None

    if retention_response.data:
        retention_days = retention_response.data[0].get(
            "card_retention_days"
        )

    if retention_days in [1, 7, 30]:
        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(days=retention_days)
        )

        data["expires_at"] = expires_at.isoformat()

    else:
        data["expires_at"] = None

    # =================================================
    # NORMALIZE QR CODES
    # =================================================

    qr_codes = _normalize_qr_codes(
        data.get("qr_codes")
    )

    if qr_codes:

        data["qr_codes"] = qr_codes

        if not data.get("qr_raw"):
            data["qr_raw"] = qr_codes[0]

    else:

        if "qr_codes" in data:
            data["qr_codes"] = []

    # =================================================
    # DEBUG LOG
    # =================================================

    print(
        "SAVE CARD - USER ID:",
        user_id,
    )

    print(
        "SAVE CARD - QR CODES:",
        data.get("qr_codes"),
    )

    print(
        "SAVE CARD - QR COUNT:",
        len(data.get("qr_codes") or []),
    )

    # =================================================
    # INSERT INTO SUPABASE
    # =================================================

    response = (
        supabase
        .table(TABLE_NAME)
        .insert(data)
        .execute()
    )

    # =================================================
    # VALIDATE RESPONSE
    # =================================================

    if not response.data:

        raise Exception(
            "Failed to save business card"
        )

    saved_card = response.data[0]

    # =================================================
    # DEBUG SAVED RESULT
    # =================================================

    print(
        "SAVED CARD ID:",
        saved_card.get("id"),
    )

    print(
        "SAVED CARD USER ID:",
        saved_card.get("user_id"),
    )

    print(
        "SAVED QR CODES:",
        saved_card.get("qr_codes"),
    )

    print(
        "SAVED QR COUNT:",
        len(saved_card.get("qr_codes") or []),
    )

    return saved_card

# =====================================================
# DELETE EXPIRED BUSINESS CARDS
# =====================================================

def delete_expired_cards(
    user_id: str,
):
    """
    Delete business cards whose retention
    period has expired.
    """

    now = datetime.now(
        timezone.utc
    ).isoformat()

    try:
        (
            supabase
            .table(TABLE_NAME)
            .delete()
            .eq(
                "user_id",
                user_id,
            )
            .lte(
                "expires_at",
                now,
            )
            .execute()
        )

    except Exception as e:
        print(
            "DELETE EXPIRED CARDS ERROR:",
            repr(e),
        )

# =====================================================
# GET USER'S BUSINESS CARDS
# =====================================================
def get_all_cards(
    user_id: str,
):
    """
    Fetch only active business cards belonging
    to the currently logged-in user.

    Expired cards are removed before fetching.
    """

    # =================================================
    # DELETE EXPIRED CARDS FIRST
    # =================================================

    delete_expired_cards(
        user_id
    )

    # =================================================
    # FETCH REMAINING CARDS
    # =================================================

    response = (
        supabase
        .table(TABLE_NAME)
        .select("*")
        .eq(
            "user_id",
            user_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    return response.data or []

# =====================================================
# DELETE USER'S BUSINESS CARD
# =====================================================

def delete_card(
    card_id: str,
    user_id: str,
):
    """
    Delete a card only when it belongs
    to the currently logged-in user.
    """

    response = (
        supabase
        .table(TABLE_NAME)
        .delete()
        .eq(
            "id",
            card_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )

    return bool(response.data)