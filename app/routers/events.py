from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.deps import require_admin
from app.models.event import Event
from app.models.user import User

router = APIRouter(prefix="/events", tags=["events"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class EventCreate(BaseModel):
    slug: str
    title: str
    description: str = ""
    logo_url: str = ""
    youtube_video_id: str = ""
    start_date: datetime
    end_date: datetime


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    youtube_video_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize(e: Event) -> dict:
    return {
        "id": str(e.id),
        "slug": e.slug,
        "title": e.title,
        "description": e.description,
        "logo_url": e.logo_url,
        "youtube_video_id": e.youtube_video_id,
        "start_date": e.start_date.isoformat(),
        "end_date": e.end_date.isoformat(),
    }


# ── Public endpoints ──────────────────────────────────────────────────────────

@router.get("/active")
async def get_active_event():
    """Return the most recently started event whose end_date is still in the future.
    Returns 404 if no such event exists.
    """
    now = datetime.now(timezone.utc)
    events = await Event.find(Event.end_date >= now).sort(-Event.start_date).to_list()
    if not events:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active event")
    return _serialize(events[0])


@router.get("/{slug}")
async def get_event(slug: str):
    event = await Event.find_one(Event.slug == slug)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return _serialize(event)


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.get("/")
async def list_events(_admin: User = Depends(require_admin)):
    events = await Event.find().sort(-Event.start_date).to_list()
    return [_serialize(e) for e in events]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_event(body: EventCreate, _admin: User = Depends(require_admin)):
    existing = await Event.find_one(Event.slug == body.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An event with slug '{body.slug}' already exists",
        )
    event = Event(**body.model_dump())
    await event.insert()
    return _serialize(event)


@router.patch("/{slug}")
async def update_event(slug: str, body: EventUpdate, _admin: User = Depends(require_admin)):
    event = await Event.find_one(Event.slug == slug)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(event, field, value)
    await event.save()
    return _serialize(event)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(slug: str, _admin: User = Depends(require_admin)):
    event = await Event.find_one(Event.slug == slug)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    await event.delete()
