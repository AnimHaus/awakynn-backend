from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.models.product import Product
from app.models.order import Order
from app.models.user import User
from app.models.class_session import ClassSession
from app.models.site_settings import SiteSettings
from app.models.contact import ContactMessage, TestimonialSubmission

_client: AsyncIOMotorClient | None = None


async def connect_db() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.MONGODB_URL)
    await init_beanie(
        database=_client[settings.DB_NAME],
        document_models=[Product, Order, User, ClassSession, SiteSettings, ContactMessage, TestimonialSubmission],
    )


async def close_db() -> None:
    if _client:
        _client.close()
