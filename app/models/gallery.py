from datetime import datetime, timezone

from beanie import Document
from pydantic import Field


class GalleryItem(Document):
    title: str = ""
    caption: str = ""
    image_url: str
    r2_key: str = ""          # stored so we can delete from R2 later
    sort_order: int = 0       # lower = shown first
    is_visible: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "gallery"
