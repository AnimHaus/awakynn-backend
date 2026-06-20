from datetime import datetime
from beanie import Document, Indexed
from pydantic import Field


class ClassSession(Document):
    slot_id: str                    # e.g. "yoga-morning"
    day_of_week: int                # JS day index 0=Sun…6=Sat
    occurrence_date: datetime       # UTC datetime of class start
    end_date: datetime              # UTC datetime of class end
    title: str = ""
    meet_link: str = ""
    generated_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "class_sessions"
