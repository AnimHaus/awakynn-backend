import uuid
from datetime import datetime, timezone
from typing import List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import require_admin
from app.models.class_session import ClassSession
from app.models.user import User
from app.schemas.class_session import ClassSessionOut, GenerateRequest
from app.config import settings

router = APIRouter(prefix="/classes", tags=["classes"])


def _serialize(s: ClassSession) -> dict:
    return {
        "id": str(s.id),
        "slot_id": s.slot_id,
        "day_of_week": s.day_of_week,
        "occurrence_date": s.occurrence_date,
        "end_date": s.end_date,
        "title": s.title,
        "meet_link": s.meet_link,
        "generated_at": s.generated_at,
        "created_at": s.created_at,
    }


async def _generate_meet(title: str, start_dt: datetime, end_dt: datetime) -> str:
    """Generate a Google Meet link via the Calendar API."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_info(
            {
                "type": "service_account",
                "client_email": settings.GOOGLE_SERVICE_ACCOUNT_EMAIL,
                "private_key": settings.GOOGLE_PRIVATE_KEY.replace("\\n", "\n"),
                "token_uri": "https://oauth2.googleapis.com/token",
            },
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        service = build("calendar", "v3", credentials=creds)
        event = (
            service.events()
            .insert(
                calendarId=settings.GOOGLE_CALENDAR_ID,
                conferenceDataVersion=1,
                body={
                    "summary": title,
                    "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
                    "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
                    "conferenceData": {
                        "createRequest": {
                            "requestId": str(uuid.uuid4()),
                            "conferenceSolutionKey": {"type": "hangoutsMeet"},
                        }
                    },
                },
            )
            .execute()
        )
        for ep in event.get("conferenceData", {}).get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                return ep["uri"]
        raise ValueError("No video entry point")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Google Meet generation failed: {e}",
        )


# ── Public: list all sessions (bulletin board) ────────────────────────────────

@router.get("/sessions/board", response_model=List[ClassSessionOut])
async def board_sessions():
    """
    Public endpoint — returns all sessions sorted by created_at descending
    (most recently scheduled class first) for the bulletin board page.
    """
    sessions = await ClassSession.find().sort(-ClassSession.created_at).to_list()
    return [_serialize(s) for s in sessions]


# ── Public: fetch next-occurrence meet link (auto-generates if missing) ───────

@router.get("/sessions/next", response_model=ClassSessionOut)
async def get_next_session(
    slot_id: str = Query(...),
    occurrence_iso: str = Query(...),
    end_iso: str = Query(...),
    title: str = Query(...),
    day_of_week: int = Query(...),
):
    """
    Returns the ClassSession for the given slot + occurrence.
    If no record exists, auto-generates a Google Meet link and stores it.
    """
    occurrence_date = datetime.fromisoformat(occurrence_iso.replace("Z", "+00:00")).replace(tzinfo=None)
    end_date = datetime.fromisoformat(end_iso.replace("Z", "+00:00")).replace(tzinfo=None)

    # Try to find existing session
    existing = await ClassSession.find_one(
        ClassSession.slot_id == slot_id,
        ClassSession.occurrence_date == occurrence_date,
    )
    if existing:
        return _serialize(existing)

    # Auto-generate
    meet_link = await _generate_meet(title, occurrence_date, end_date)
    session = ClassSession(
        slot_id=slot_id,
        day_of_week=day_of_week,
        occurrence_date=occurrence_date,
        end_date=end_date,
        title=title,
        meet_link=meet_link,
        generated_at=datetime.utcnow(),
    )
    await session.insert()
    return _serialize(session)


# ── Admin: list all sessions ──────────────────────────────────────────────────

@router.get("/sessions", response_model=List[ClassSessionOut])
async def list_sessions(
    upcoming_only: bool = Query(True),
    _admin: User = Depends(require_admin),
):
    now = datetime.utcnow()
    query = (
        ClassSession.find(ClassSession.occurrence_date >= now)
        if upcoming_only
        else ClassSession.find()
    )
    sessions = await query.sort(+ClassSession.occurrence_date).to_list()
    return [_serialize(s) for s in sessions]


# ── Admin: manually generate / regenerate a session ──────────────────────────

@router.post("/sessions/generate", response_model=ClassSessionOut, status_code=status.HTTP_201_CREATED)
async def generate_session(
    body: GenerateRequest,
    _admin: User = Depends(require_admin),
):
    occurrence_date = body.occurrence_date.replace(tzinfo=None)
    end_date = body.end_date.replace(tzinfo=None)

    existing = await ClassSession.find_one(
        ClassSession.slot_id == body.slot_id,
        ClassSession.occurrence_date == occurrence_date,
    )

    meet_link = await _generate_meet(body.title, occurrence_date, end_date)

    if existing:
        existing.meet_link = meet_link
        existing.generated_at = datetime.utcnow()
        await existing.save()
        return _serialize(existing)

    session = ClassSession(
        slot_id=body.slot_id,
        day_of_week=body.day_of_week,
        occurrence_date=occurrence_date,
        end_date=end_date,
        title=body.title,
        meet_link=meet_link,
        generated_at=datetime.utcnow(),
    )
    await session.insert()
    return _serialize(session)


# ── Admin: delete a session ───────────────────────────────────────────────────

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    _admin: User = Depends(require_admin),
):
    session = await ClassSession.get(PydanticObjectId(session_id))
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await session.delete()
