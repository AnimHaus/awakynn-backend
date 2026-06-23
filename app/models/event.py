from datetime import datetime

from beanie import Document


class Event(Document):
    slug: str          # unique URL slug, e.g. "yoga-day-2026"
    title: str
    description: str = ""
    logo_url: str = ""           # CDN URL for the navbar / event logo image
    youtube_video_id: str = ""   # YouTube video ID to embed
    start_date: datetime
    end_date: datetime

    class Settings:
        name = "events"
