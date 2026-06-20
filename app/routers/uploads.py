"""
Upload router — brand-scoped image upload endpoints.

POST /api/v1/uploads/{brand}/image
  • brand: one of grabfabs | awakynn | festiq | estra
  • Requires admin authentication
  • Returns: { "url": "<public CDN url>" }

The brand slug maps to its own R2 bucket via R2_BUCKET_<BRAND> in .env.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Path, UploadFile

from app.core.deps import require_admin
from app.models.user import User
from app.services.r2 import upload_image, delete_image
from app.config import settings

router = APIRouter(prefix="/uploads", tags=["uploads"])

_VALID_BRANDS = {"grabfabs", "awakynn", "festiq", "estra"}


def _validate_brand(brand: str) -> str:
    if brand not in _VALID_BRANDS:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown brand '{brand}'. Valid brands: {', '.join(sorted(_VALID_BRANDS))}",
        )
    return brand


@router.post("/{brand}/image")
async def upload_brand_image(
    brand: Annotated[str, Path(description="Brand slug: grabfabs | awakynn | festiq | estra")],
    file: Annotated[UploadFile, File(description="Image file (JPEG, PNG, WebP, GIF, AVIF). Max 10 MB.")],
    _: Annotated[User, Depends(require_admin)],
    folder: str = "products",
):
    """
    Upload a product (or any) image to the specified brand's R2 bucket.

    - **brand**: target brand — determines which R2 bucket is used
    - **file**: the image to upload
    - **folder**: sub-folder inside the bucket (default: `products`)

    Returns the public CDN URL of the uploaded image.
    """
    _validate_brand(brand)
    url = await upload_image(file=file, brand=brand, folder=folder)
    return {"url": url, "brand": brand}


@router.delete("/{brand}/image")
async def delete_brand_image(
    brand: Annotated[str, Path(description="Brand slug")],
    key: str,
    _: Annotated[User, Depends(require_admin)],
):
    """
    Delete an image from the specified brand's R2 bucket by its object key
    (the path portion after the CDN domain, e.g. `products/abc123.webp`).
    """
    _validate_brand(brand)
    await delete_image(key=key, brand=brand)
    return {"deleted": key, "brand": brand}


@router.get("/brands")
async def list_configured_brands(
    _: Annotated[User, Depends(require_admin)],
):
    """Return the brands that have an R2 bucket configured."""
    return {"brands": list(settings.r2_bucket_map.keys())}
