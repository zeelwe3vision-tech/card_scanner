from typing import Optional

from pydantic import BaseModel, ConfigDict


class CardCreate(BaseModel):
    owner_name: str
    company_name: Optional[str] = None
    designation: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gst_number: Optional[str] = None
    company_logo: Optional[str] = None
    instagram_url: Optional[str] = None
    website_url: Optional[str] = None
    facebook_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    other_details: Optional[str] = None
    qr_raw: Optional[str] = None
    qr_codes: Optional[list[str]] = None

    model_config = ConfigDict(extra="ignore")


class UrlRequest(BaseModel):
    url: str