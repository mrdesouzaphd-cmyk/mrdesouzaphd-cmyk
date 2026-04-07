"""SQLAlchemy database models for the ebook agent."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from config.settings import settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    projects = relationship("EbookProject", back_populates="user", cascade="all, delete-orphan")


class EbookProject(Base):
    __tablename__ = "ebook_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    language = Column(String(10), default="en")
    status = Column(
        Enum(
            "draft",
            "processing",
            "ready",
            "published",
            "error",
            name="project_status",
        ),
        default="draft",
    )
    template = Column(String(100), default="default")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="projects")
    content_items = relationship(
        "ContentItem", back_populates="project", cascade="all, delete-orphan"
    )
    ebook_files = relationship(
        "EbookFile", back_populates="project", cascade="all, delete-orphan"
    )


class ContentItem(Base):
    __tablename__ = "content_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("ebook_projects.id"), nullable=False)
    content_type = Column(
        Enum("text", "image", "video", name="content_type_enum"), nullable=False
    )
    title = Column(String(500))
    raw_text = Column(Text)
    gcs_raw_path = Column(String(1000))
    gcs_processed_path = Column(String(1000))
    ai_description = Column(Text)
    ai_caption = Column(Text)
    chapter_order = Column(Integer, default=0)
    processing_status = Column(
        Enum("pending", "processing", "completed", "error", name="processing_status"),
        default="pending",
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    project = relationship("EbookProject", back_populates="content_items")


class EbookFile(Base):
    __tablename__ = "ebook_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("ebook_projects.id"), nullable=False)
    format = Column(Enum("epub", "pdf", name="ebook_format"), nullable=False)
    gcs_path = Column(String(1000), nullable=False)
    file_size_bytes = Column(Integer)
    price = Column(Float, default=0.0)
    is_published = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    project = relationship("EbookProject", back_populates="ebook_files")


def get_engine():
    return create_engine(settings.database_url, pool_pre_ping=True)


def get_session_factory():
    engine = get_engine()
    return sessionmaker(bind=engine)


def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
