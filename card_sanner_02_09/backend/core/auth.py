from datetime import datetime, timedelta, timezone
import httpx
import jwt
from fastapi import Header, HTTPException

from backend.core.config import settings
from backend.core.supabase import supabase


ALGORITHM = "HS256"


def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )

def get_current_user(
    authorization: str | None = Header(default=None),
):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Login required",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication",
        )

    token = authorization.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid login session",
            )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Login session expired",
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid login session",
        )

    # =====================================================
    # GET USER FROM SUPABASE
    # =====================================================

    try:
        response = (
            supabase
            .table("login")
            .select("id, email, full_name")
            .eq("id", user_id)
            .execute()
        )

    except httpx.RequestError as e:
        print(
            "SUPABASE CONNECTION ERROR:",
            repr(e)
        )

        # Retry once
        try:
            response = (
                supabase
                .table("login")
                .select("id, email, full_name")
                .eq("id", user_id)
                .execute()
            )

        except httpx.RequestError as retry_error:
            print(
                "SUPABASE RETRY ERROR:",
                repr(retry_error)
            )

            raise HTTPException(
                status_code=503,
                detail="Unable to connect to database. Please try again."
            )

    if not response.data:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    return response.data[0]