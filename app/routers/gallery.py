"""
Gallery router — Awakynn photo gallery CRUD.

Public:
  GET  /api/v1/gallery/           — list visible items (sorted)
  GET  /api/v1/gallery/{id}       — single item

Admin:
  POST   /api/v1/gallery/upload   — upload image to R2 + create record
  PATCH  /api/v1/gallery/{id}     — update title / caption / sort_order / is_visible
  DELETE /api/v1/gallery/{id}     — delete record + R2 object
"""

from typing import Annotated, List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.deps import require_admin
from app.models.gallery import GalleryItem
from app.models.user import User
from app.services.r2 import delete_image, upload_image

router = APIRouter(prefix="/gallery", tags=["gallery"])


# ── Serializer ────────────────────────────────────────────────────────────────

def _serialize(item: GalleryItem) -> dict:
    return {
        "id": str(item.id),
        "title": item.title,
        "caption": item.caption,
        "image_url": item.image_url,
        "r2_key": item.r2_key,
        "sort_order": item.sort_order,
        "is_visible": item.is_visible,
        "created_at": item.created_at.isoformat(),
    }


# ── Public endpoints ──────────────────────────────────────────────────────────

@router.get("/", response_model=List[dict])
async def list_gallery(visible_only: bool = True):
    """Return gallery items ordered by sort_order ascending, then created_at descending."""
    query = (
        GalleryItem.find(GalleryItem.is_visible == True)
        if visible_only
        else GalleryItem.find()
    )
    items = await query.sort(
        [("sort_order", 1), ("created_at", -1)]
    ).to_list()
    return [_serialize(i) for i in items]


@router.get("/{item_id}", response_model=dict)
async def get_gallery_item(item_id: PydanticObjectId):
    item = await GalleryItem.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return _serialize(item)


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.post("/upload", response_model=dict, status_code=status.HTTP_201_CREATED)
async def upload_gallery_image(
    file: Annotated[UploadFile, File(description="Image file (JPEG, PNG, WebP). Max 10 MB.")],
    _: Annotated[User, Depends(require_admin)],
    title: str = Form(""),
    caption: str = Form(""),
    sort_order: int = Form(0),
):
    """Upload an image to R2 (awakynn bucket, gallery/ folder) and create a gallery record."""
    public_url = await upload_image(file=file, brand="awakynn", folder="gallery")

    # Derive the R2 key from the CDN URL (everything after the bucket domain)
    # URL shape: https://pub-<account>.r2.dev/<key>
    from urllib.parse import urlparse
    r2_key = urlparse(public_url).path.lstrip("/")

    item = GalleryItem(
        title=title,
        caption=caption,
        image_url=public_url,
        r2_key=r2_key,
        sort_order=sort_order,
    )
    await item.insert()
    return _serialize(item)


class GalleryPatch(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    sort_order: Optional[int] = None
    is_visible: Optional[bool] = None


@router.patch("/{item_id}", response_model=dict)
async def update_gallery_item(
    item_id: PydanticObjectId,
    body: GalleryPatch,
    _: Annotated[User, Depends(require_admin)],
):
    item = await GalleryItem.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    updates = body.model_dump(exclude_none=True)
    if updates:
        await item.set(updates)
        await item.sync()

    return _serialize(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gallery_item(
    item_id: PydanticObjectId,
    _: Annotated[User, Depends(require_admin)],
):
    item = await GalleryItem.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # Delete from R2 if we have the key
    if item.r2_key:
        try:
            await delete_image(key=item.r2_key, brand="awakynn")
        except HTTPException:
            pass  # Don't block DB deletion if R2 removal fails

    await item.delete()
