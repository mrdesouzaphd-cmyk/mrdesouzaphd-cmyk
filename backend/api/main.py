"""FastAPI application entry point for the Content-to-Ebook Agent."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router
from config.settings import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI-powered agent that receives text, images, and videos, "
        "organizes them into ebook format (EPUB/PDF), and makes them "
        "available for sale via Google Cloud."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "healthy", "version": settings.app_version}
