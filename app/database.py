from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.models.product import Product
from app.models.order import Order
from app.models.user import User
from app.models.class_session import ClassSession
from app.models.contact import ContactMessage, TestimonialSubmission
from app.models.event import Event
from app.models.site_settings import SiteSettings
from app.models.gallery import GalleryItem

_client: AsyncIOMotorClient | None = None


async def connect_db() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.MONGODB_URL)

    # awakynn — yoga classes, contact/testimonials, site settings
    await init_beanie(
        database=_client[settings.DB_AWAKYNN],
        document_models=[ClassSession, ContactMessage, TestimonialSubmission, SiteSettings, Event, GalleryItem],
    )

    # grabfabs — products and orders
    await init_beanie(
        database=_client[settings.DB_GRABFABS],
        document_models=[Product, Order],
    )

    # shared — user accounts (used by both brands)
    await init_beanie(
        database=_client[settings.DB_SHARED],
        document_models=[User],
    )


async def close_db() -> None:
    if _client:
        _client.close()
