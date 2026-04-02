"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


# --- User ---
class UserCreate(BaseModel):
    email: str
    name: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Ebook Project ---
class ProjectCreate(BaseModel):
    title: str
    description: str | None = None
    language: str = "en"
    template: str = "default"


class ProjectUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    language: str | None = None
    template: str | None = None


class ProjectResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: str | None
    language: str
    status: str
    template: str
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


# --- Content Item ---
class ContentItemCreate(BaseModel):
    content_type: str
    title: str | None = None
    raw_text: str | None = None
    chapter_order: int = 0


class ContentItemResponse(BaseModel):
    id: UUID
    project_id: UUID
    content_type: str
    title: str | None
    raw_text: str | None
    gcs_raw_path: str | None
    gcs_processed_path: str | None
    ai_description: str | None
    ai_caption: str | None
    chapter_order: int
    processing_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Ebook File ---
class EbookFileResponse(BaseModel):
    id: UUID
    project_id: UUID
    format: str
    gcs_path: str
    file_size_bytes: int | None
    price: float
    is_published: int
    created_at: datetime

    model_config = {"from_attributes": True}


class GenerateEbookRequest(BaseModel):
    formats: list[str] = ["epub", "pdf"]


class PublishRequest(BaseModel):
    price: float
    ebook_file_id: UUID
