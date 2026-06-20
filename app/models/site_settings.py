from beanie import Document
from pydantic import Field


class SiteSettings(Document):
    key: str          # e.g. "season"
    value: str        # e.g. "monsoon"

    class Settings:
        name = "site_settings"
