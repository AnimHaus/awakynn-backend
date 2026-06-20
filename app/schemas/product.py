from typing import List, Optional
from pydantic import BaseModel


class SkuSchema(BaseModel):
    label: str
    price: float


class ProductCreate(BaseModel):
    slug: str
    name: str
    tagline: str
    description: str
    long_description: str = ""
    highlights: List[str] = []
    nutrition_note: str = ""
    pricing: List[SkuSchema] = []
    color: str = "#1a5c28"
    accent: str = "#c87c2e"
    image: str = ""
    hero_image: str = ""
    stock: int = 100
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    long_description: Optional[str] = None
    highlights: Optional[List[str]] = None
    nutrition_note: Optional[str] = None
    pricing: Optional[List[SkuSchema]] = None
    color: Optional[str] = None
    accent: Optional[str] = None
    image: Optional[str] = None
    hero_image: Optional[str] = None
    stock: Optional[int] = None
    is_active: Optional[bool] = None


class ProductOut(BaseModel):
    id: str
    slug: str
    name: str
    tagline: str
    description: str
    long_description: str
    highlights: List[str]
    nutrition_note: str
    pricing: List[dict]
    color: str
    accent: str
    image: str
    hero_image: str
    stock: int
    is_active: bool

    model_config = {"from_attributes": True}
