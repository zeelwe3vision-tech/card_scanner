from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

from backend.core.supabase import supabase
from backend.core.auth import (
    create_access_token,
    get_current_user,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# ==========================================
# Request Models
# ==========================================

class SignupRequest(BaseModel):
    full_name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str

class LogoutRequest(BaseModel):
    user_id: str

class RetentionRequest(BaseModel):
    retention_days: int | None = None

# ==========================================
# CREATE ACCOUNT
# ==========================================

@router.post("/signup")
def signup(data: SignupRequest):
    try:
        email = data.email.strip().lower()

        # Check if account already exists
        existing_user = (
            supabase
            .table("login")
            .select("id")
            .ilike("email", email)
            .execute()
        )

        if existing_user.data:
            raise HTTPException(
                status_code=409,
                detail="Account already exists with this email"
            )

        # Create new account
        response = (
            supabase
            .table("login")
            .insert({
                "full_name": data.full_name.strip(),
                "email": email,
                "password": data.password
            })
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=500,
                detail="Unable to create account"
            )

        user = response.data[0]

        return {
            "success": True,
            "message": "Account created successfully",
            "user": {
                "id": user.get("id"),
                "full_name": user.get("full_name"),
                "email": user.get("email")
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        print("SIGNUP ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ==========================================
# LOGIN
# ==========================================

@router.post("/login")
def login(data: LoginRequest):
    try:
        email = data.email.strip()

        # Find user by email
        response = (
            supabase
            .table("login")
            .select("*")
            .ilike("email", email)
            .execute()
        )

        # User does not exist
        if not response.data:
            raise HTTPException(
                status_code=401,
                detail="Account not found. Please create an account."
            )

        user = response.data[0]

        # Password does not match
        if user.get("password") != data.password:
            raise HTTPException(
                status_code=401,
                detail="Incorrect password"
            )
        access_token = create_access_token(
            str(user.get("id"))
        )

        # Successful login
        return {
            "success": True,
            "message": "Login successful",
            "user": {
                "id": user.get("id"),
                "email": user.get("email"),
                "full_name": user.get("full_name")
            },
            "access_token": access_token
        }

    except HTTPException:
        raise

    except Exception as e:
        print("LOGIN ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.post("/logout")
def logout(data: LogoutRequest):
    try:
        # Find the current user
        response = (
            supabase
            .table("login")
            .select("id, email, full_name")
            .eq("id", data.user_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        user = response.data[0]

        # Logout does NOT delete the account.
        # The frontend will clear the logged-in session.
        return {
            "success": True,
            "message": "Logout successful",
            "user": {
                "id": user.get("id"),
                "email": user.get("email"),
                "full_name": user.get("full_name"),
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        print("LOGOUT ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ==========================================
# GET CARD RETENTION SETTING
# ==========================================

@router.get("/retention")
def get_retention(
    current_user: dict = Depends(get_current_user),
):
    try:
        response = (
            supabase
            .table("login")
            .select("card_retention_days")
            .eq("id", current_user["id"])
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        return {
            "success": True,
            "retention_days": response.data[0].get(
                "card_retention_days"
            )
        }

    except HTTPException:
        raise

    except Exception as e:
        print("GET RETENTION ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ==========================================
# UPDATE CARD RETENTION SETTING
# ==========================================

@router.put("/retention")
def update_retention(
    data: RetentionRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        retention_days = data.retention_days

        if retention_days not in [1, 7, 30, None]:
            raise HTTPException(
                status_code=400,
                detail="Retention must be 1, 7, 30 days or Never"
            )

        user_id = str(current_user["id"])

        # Save preference for this user
        (
            supabase
            .table("login")
            .update({
                "card_retention_days": retention_days
            })
            .eq("id", user_id)
            .execute()
        )

        # ==========================================
        # NEVER
        # ==========================================

        if retention_days is None:
            (
                supabase
                .table("business_cards")
                .update({
                    "expires_at": None
                })
                .eq("user_id", user_id)
                .execute()
            )

        # ==========================================
        # 1 / 7 / 30 DAYS
        # ==========================================

        else:
            cards_response = (
                supabase
                .table("business_cards")
                .select("id, created_at")
                .eq("user_id", user_id)
                .execute()
            )

            for card in cards_response.data or []:
                created_at = card.get("created_at")

                if not created_at:
                    continue

                created_datetime = datetime.fromisoformat(
                    created_at.replace(
                        "Z",
                        "+00:00"
                    )
                )

                expires_at = (
                    created_datetime
                    + timedelta(
                        days=retention_days
                    )
                )

                (
                    supabase
                    .table("business_cards")
                    .update({
                        "expires_at": expires_at.isoformat()
                    })
                    .eq("id", card["id"])
                    .eq("user_id", user_id)
                    .execute()
                )

            # ==========================================
            # DELETE CARDS THAT ARE ALREADY EXPIRED
            # ==========================================

            now = datetime.now(
                timezone.utc
            ).isoformat()

            (
                supabase
                .table("business_cards")
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

        return {
            "success": True,
            "message": "Card retention setting updated successfully",
            "retention_days": retention_days
        }

    except HTTPException:
        raise

    except Exception as e:
        print("UPDATE RETENTION ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )