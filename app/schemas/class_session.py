from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ClassSessionOut(BaseModel):
    id: str
    slot_id: str
    day_of_week: int
    occurrence_date: datetime
    end_date: datetime
    title: str
    meet_link: str
    generated_at: Optional[datetime]
    created_at: datetime


class GenerateRequest(BaseModel):
    slot_id: str
    day_of_week: int
    occurrence_date: datetime   # UTC
    end_date: datetime          # UTC
    title: str
