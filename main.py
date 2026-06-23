from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import close_db, connect_db
from app.routers import auth, classes, contact, events as events_router, orders, products, settings as settings_router, uploads


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="Grabfabs API",
    version="1.0.0",
    description="Ecommerce backend for Grabfabs — Feel Good, On the Go foods.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")
app.include_router(uploads.router, prefix="/api/v1")
app.include_router(classes.router, prefix="/api/v1")
app.include_router(contact.router, prefix="/api/v1")
app.include_router(events_router.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
