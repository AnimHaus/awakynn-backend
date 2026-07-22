from typing import List, Optional
from datetime import datetime, timezone
from beanie import Document, Indexed
from pydantic import EmailStr, Field


class Address(Document):
    label: str = "Home"
    full_name: str
    phone: str
    line1: str
    line2: str = ""
    city: str
    state: str
    pincode: str
    country: str = "India"

    class Settings:
        is_root = False


class User(Document):
    email: Indexed(EmailStr, unique=True)  # type: ignore[valid-type]
    hashed_password: str = ""
    full_name: str
    phone: str = ""
    age: Optional[int] = None
    gender: Optional[str] = None
    medical_history: str = ""
    addresses: List[dict] = []
    is_active: bool = True
    is_admin: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"
