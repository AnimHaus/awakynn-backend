from datetime import datetime
from typing import Literal, Optional
from beanie import Document
from pydantic import Field


class ContactMessage(Document):
    name: str
    email: str
    phone: str = ""
    interest: str = ""
    message: str
    status: Literal["new", "read", "replied"] = "new"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "contact_messages"


class TestimonialSubmission(Document):
    name: str
    age: Optional[int] = None
    note: str = ""          # e.g. "Neha's Mom"
    message: str
    approved: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "testimonial_submissions"
