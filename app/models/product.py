from typing import List, Optional
from beanie import Document, Indexed
from pydantic import Field


class Sku(Document):
    label: str
    price: float

    class Settings:
        # Embedded — not a top-level collection
        is_root = False


class Product(Document):
    slug: Indexed(str, unique=True)  # type: ignore[valid-type]
    name: str
    tagline: str
    description: str
    long_description: str = Field(alias="longDescription", default="")
    highlights: List[str] = []
    nutrition_note: str = Field(alias="nutritionNote", default="")
    pricing: List[dict] = []  # [{label: str, price: float}]
    color: str = "#1a5c28"
    accent: str = "#c87c2e"
    image: str = ""
    hero_image: str = Field(alias="heroImage", default="")
    stock: int = 100
    is_active: bool = True

    class Settings:
        name = "products"

    class Config:
        populate_by_name = True
