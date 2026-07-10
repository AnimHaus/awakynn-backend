from typing import Annotated, List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import get_current_user, require_admin
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


def _serialize(p: Product) -> dict:
    return {
        "id": str(p.id),
        "slug": p.slug,
        "name": p.name,
        "tagline": p.tagline,
        "description": p.description,
        "long_description": p.long_description,
        "highlights": p.highlights,
        "nutrition_note": p.nutrition_note,
        "pricing": p.pricing,
        "color": p.color,
        "accent": p.accent,
        "image": p.image,
        "hero_image": p.hero_image,
        "stock": p.stock,
        "is_active": p.is_active,
    }


@router.get("/", response_model=List[ProductOut])
async def list_products(
    active_only: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    query = Product.find(Product.is_active == True) if active_only else Product.find()
    products = await query.skip(skip).limit(limit).to_list()
    return [_serialize(p) for p in products]


@router.get("/{slug}", response_model=ProductOut)
async def get_product(slug: str):
    product = await Product.find_one(Product.slug == slug)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return _serialize(product)


@router.post("/", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreate,
    _: Annotated[User, Depends(require_admin)],
):
    existing = await Product.find_one(Product.slug == body.slug)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")
    product = Product(
        slug=body.slug,
        name=body.name,
        tagline=body.tagline,
        description=body.description,
        long_description=body.long_description,
        highlights=body.highlights,
        nutrition_note=body.nutrition_note,
        pricing=[s.model_dump() for s in body.pricing],
        color=body.color,
        accent=body.accent,
        image=body.image,
        hero_image=body.hero_image,
        stock=body.stock,
        is_active=body.is_active,
    )
    await product.insert()
    return _serialize(product)


@router.patch("/{slug}", response_model=ProductOut)
async def update_product(
    slug: str,
    body: ProductUpdate,
    _: Annotated[User, Depends(require_admin)],
):
    product = await Product.find_one(Product.slug == slug)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    update_data = body.model_dump(exclude_unset=True)
    if "pricing" in update_data:
        update_data["pricing"] = [s.model_dump() for s in body.pricing]
    for field_name, value in update_data.items():
        setattr(product, field_name, value)
    await product.save()
    return _serialize(product)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    slug: str,
    _: Annotated[User, Depends(require_admin)],
):
    product = await Product.find_one(Product.slug == slug)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await product.delete()
