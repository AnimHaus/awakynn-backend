from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import require_admin
from app.models.site_settings import SiteSettings
from app.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])

VALID_SEASONS = {"summer", "monsoon", "autumn", "winter"}


async def _get_or_create(key: str, default: str) -> SiteSettings:
    doc = await SiteSettings.find_one(SiteSettings.key == key)
    if not doc:
        doc = SiteSettings(key=key, value=default)
        await doc.insert()
    return doc


# ── Public: read current season ───────────────────────────────────────────────

@router.get("/season")
async def get_season():
    doc = await _get_or_create("season", "summer")
    return {"season": doc.value}


# ── Admin: update season ──────────────────────────────────────────────────────

class SeasonUpdate(BaseModel):
    season: str


@router.patch("/season")
async def set_season(body: SeasonUpdate, _admin: User = Depends(require_admin)):
    if body.season not in VALID_SEASONS:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid season. Must be one of: {', '.join(VALID_SEASONS)}",
        )
    doc = await _get_or_create("season", "summer")
    doc.value = body.season
    await doc.save()
    return {"season": doc.value}
