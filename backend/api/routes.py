"""FastAPI routes for the Content-to-Ebook Agent backend."""

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.models.database import (
    ContentItem,
    EbookFile,
    EbookProject,
    User,
    get_session_factory,
)
from backend.models.schemas import (
    ContentItemCreate,
    ContentItemResponse,
    EbookFileResponse,
    GenerateEbookRequest,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    PublishRequest,
    UserCreate,
    UserResponse,
)
from backend.services.pubsub import PubSubService
from backend.services.storage import StorageService
from config.settings import settings

logger = structlog.get_logger()

router = APIRouter()

SessionFactory = None


def get_db() -> Session:
    global SessionFactory
    if SessionFactory is None:
        SessionFactory = get_session_factory()
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


def get_storage() -> StorageService:
    return StorageService()


def get_pubsub() -> PubSubService:
    return PubSubService()


# ──────────────────────────────────────────────
# User endpoints
# ──────────────────────────────────────────────


@router.post("/users", response_model=UserResponse, tags=["Users"])
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    user = User(email=payload.email, name=payload.name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{user_id}", response_model=UserResponse, tags=["Users"])
def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ──────────────────────────────────────────────
# Ebook Project endpoints
# ──────────────────────────────────────────────


@router.post("/projects", response_model=ProjectResponse, tags=["Projects"])
def create_project(payload: ProjectCreate, user_id: str, db: Session = Depends(get_db)):
    project = EbookProject(
        user_id=user_id,
        title=payload.title,
        description=payload.description,
        language=payload.language,
        template=payload.template,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("project_created", project_id=str(project.id), title=project.title)
    return project


@router.get("/projects/{project_id}", response_model=ProjectResponse, tags=["Projects"])
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(EbookProject).filter(EbookProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/projects", response_model=list[ProjectResponse], tags=["Projects"])
def list_projects(user_id: str, db: Session = Depends(get_db)):
    return db.query(EbookProject).filter(EbookProject.user_id == user_id).all()


@router.patch("/projects/{project_id}", response_model=ProjectResponse, tags=["Projects"])
def update_project(
    project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)
):
    project = db.query(EbookProject).filter(EbookProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


# ──────────────────────────────────────────────
# Content upload endpoints
# ──────────────────────────────────────────────


@router.post(
    "/projects/{project_id}/content/text",
    response_model=ContentItemResponse,
    tags=["Content"],
)
def upload_text(
    project_id: str,
    title: str = Form(""),
    raw_text: str = Form(...),
    chapter_order: int = Form(0),
    db: Session = Depends(get_db),
):
    """Upload text content for an ebook chapter."""
    item = ContentItem(
        project_id=project_id,
        content_type="text",
        title=title,
        raw_text=raw_text,
        chapter_order=chapter_order,
        processing_status="completed",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    logger.info("text_uploaded", project_id=project_id, item_id=str(item.id))
    return item


@router.post(
    "/projects/{project_id}/content/media",
    response_model=ContentItemResponse,
    tags=["Content"],
)
async def upload_media(
    project_id: str,
    file: UploadFile = File(...),
    title: str = Form(""),
    chapter_order: int = Form(0),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    pubsub: PubSubService = Depends(get_pubsub),
):
    """Upload an image or video file for the ebook."""
    content_type = file.content_type or ""

    if content_type in settings.allowed_image_types:
        item_type = "image"
    elif content_type in settings.allowed_video_types:
        item_type = "video"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. "
            f"Allowed: {settings.allowed_image_types + settings.allowed_video_types}",
        )

    file_data = await file.read()
    if len(file_data) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")

    gcs_path = storage.upload_raw_content(
        project_id=project_id,
        file_data=file_data,
        filename=file.filename or "upload",
        content_type=content_type,
    )

    item = ContentItem(
        project_id=project_id,
        content_type=item_type,
        title=title or file.filename,
        gcs_raw_path=gcs_path,
        chapter_order=chapter_order,
        processing_status="pending",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # Trigger async AI processing via Pub/Sub
    pubsub.publish_content_ingested(
        project_id=project_id,
        content_item_id=str(item.id),
        content_type=item_type,
    )

    logger.info(
        "media_uploaded",
        project_id=project_id,
        item_id=str(item.id),
        type=item_type,
    )
    return item


@router.get(
    "/projects/{project_id}/content",
    response_model=list[ContentItemResponse],
    tags=["Content"],
)
def list_content(project_id: str, db: Session = Depends(get_db)):
    return (
        db.query(ContentItem)
        .filter(ContentItem.project_id == project_id)
        .order_by(ContentItem.chapter_order)
        .all()
    )


# ──────────────────────────────────────────────
# Ebook generation & publishing
# ──────────────────────────────────────────────


@router.post(
    "/projects/{project_id}/generate",
    response_model=list[EbookFileResponse],
    tags=["Ebook"],
)
def generate_ebook(
    project_id: str,
    payload: GenerateEbookRequest,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    pubsub: PubSubService = Depends(get_pubsub),
):
    """Trigger ebook generation from all project content."""
    from ebook_generator.generator import EbookGenerator

    project = db.query(EbookProject).filter(EbookProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content_items = (
        db.query(ContentItem)
        .filter(ContentItem.project_id == project_id)
        .order_by(ContentItem.chapter_order)
        .all()
    )

    if not content_items:
        raise HTTPException(status_code=400, detail="No content in project")

    project.status = "processing"
    db.commit()

    generator = EbookGenerator(storage_service=storage)
    generated_files = []

    for fmt in payload.formats:
        ebook_data, filename = generator.generate(
            project=project,
            content_items=content_items,
            output_format=fmt,
        )
        content_type = (
            "application/epub+zip" if fmt == "epub" else "application/pdf"
        )
        gcs_path = storage.upload_ebook(
            project_id=project_id,
            file_data=ebook_data,
            filename=filename,
            content_type=content_type,
        )
        ebook_file = EbookFile(
            project_id=project_id,
            format=fmt,
            gcs_path=gcs_path,
            file_size_bytes=len(ebook_data),
        )
        db.add(ebook_file)
        db.commit()
        db.refresh(ebook_file)
        generated_files.append(ebook_file)

        pubsub.publish_ebook_ready(
            project_id=project_id,
            ebook_file_id=str(ebook_file.id),
            format=fmt,
        )

    project.status = "ready"
    db.commit()

    logger.info("ebook_generated", project_id=project_id, formats=payload.formats)
    return generated_files


@router.post(
    "/projects/{project_id}/publish",
    response_model=EbookFileResponse,
    tags=["Ebook"],
)
def publish_ebook(
    project_id: str,
    payload: PublishRequest,
    db: Session = Depends(get_db),
):
    """Set price and publish an ebook for sale."""
    ebook_file = (
        db.query(EbookFile)
        .filter(
            EbookFile.id == str(payload.ebook_file_id),
            EbookFile.project_id == project_id,
        )
        .first()
    )
    if not ebook_file:
        raise HTTPException(status_code=404, detail="Ebook file not found")

    ebook_file.price = payload.price
    ebook_file.is_published = 1

    project = db.query(EbookProject).filter(EbookProject.id == project_id).first()
    if project:
        project.status = "published"

    db.commit()
    db.refresh(ebook_file)
    logger.info("ebook_published", project_id=project_id, price=payload.price)
    return ebook_file


@router.get(
    "/projects/{project_id}/download/{ebook_file_id}",
    tags=["Ebook"],
)
def get_download_url(
    project_id: str,
    ebook_file_id: str,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
):
    """Get a temporary signed download URL for an ebook."""
    ebook_file = (
        db.query(EbookFile)
        .filter(
            EbookFile.id == ebook_file_id,
            EbookFile.project_id == project_id,
        )
        .first()
    )
    if not ebook_file:
        raise HTTPException(status_code=404, detail="Ebook file not found")

    url = storage.generate_signed_url(ebook_file.gcs_path)
    return {"download_url": url, "format": ebook_file.format}


# ──────────────────────────────────────────────
# Platform validation & distribution
# ──────────────────────────────────────────────


@router.get("/platforms", tags=["Platforms"])
def list_platforms():
    """List all supported publishing platforms with their 2026 specs."""
    from backend.services.platform_formatter import PlatformFormatter

    formatter = PlatformFormatter()
    return formatter.get_all_platforms()


@router.get("/platforms/{platform_name}/spec", tags=["Platforms"])
def get_platform_spec(platform_name: str):
    """Get detailed 2026 format specification for a platform."""
    from backend.services.platform_formatter import Platform, PlatformFormatter

    try:
        platform = Platform(platform_name)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown platform: {platform_name}. Use /platforms to see available options.",
        )

    formatter = PlatformFormatter()
    spec = formatter.get_platform_spec(platform)
    return {
        "platform": spec.platform.value,
        "supported_formats": spec.supported_formats,
        "max_file_size_mb": spec.max_file_size_mb,
        "cover_image_specs": spec.cover_image_specs,
        "metadata_fields": spec.metadata_fields,
        "content_requirements": spec.content_requirements,
        "drm_options": spec.drm_options,
        "pricing_currency": spec.pricing_currency,
        "notes": spec.notes,
    }


@router.post(
    "/projects/{project_id}/validate-platform/{platform_name}",
    tags=["Platforms"],
)
def validate_for_platform(
    project_id: str,
    platform_name: str,
    db: Session = Depends(get_db),
):
    """Validate an ebook project against a specific platform's 2026 requirements."""
    from backend.services.platform_formatter import Platform, PlatformFormatter

    try:
        platform = Platform(platform_name)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform_name}")

    project = db.query(EbookProject).filter(EbookProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ebook_files = (
        db.query(EbookFile).filter(EbookFile.project_id == project_id).all()
    )
    if not ebook_files:
        raise HTTPException(status_code=400, detail="No ebook files generated yet")

    formatter = PlatformFormatter()
    results = []

    for ebook_file in ebook_files:
        metadata = {
            "title": project.title,
            "author": "DrDeSouzAI",
            "description": project.description or "",
            "language": project.language,
        }

        result = formatter.validate_for_platform(
            platform=platform,
            ebook_format=ebook_file.format,
            file_size_bytes=ebook_file.file_size_bytes or 0,
            metadata=metadata,
            has_toc=True,
            has_cover=False,  # TODO: track cover image in project
            images_have_alt_text=True,
        )
        results.append({
            "ebook_file_id": str(ebook_file.id),
            "format": ebook_file.format,
            "platform": result.platform.value,
            "is_valid": result.is_valid,
            "metadata_ready": result.metadata_ready,
            "format_ready": result.format_ready,
            "issues": [
                {"severity": i.severity, "field": i.field, "message": i.message}
                for i in result.issues
            ],
        })

    return results


@router.post(
    "/projects/{project_id}/export/{export_type}",
    tags=["Export"],
)
def export_for_tool(
    project_id: str,
    export_type: str,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
):
    """Export project content for external tools.

    Supported export_type values:
    - 'pages': DOCX file for Apple Pages
    - 'canva': Structured JSON for Canva templates
    - 'audiobook': Generate audiobook MP3 via Text-to-Speech
    """
    from backend.services.distribution import DistributionService

    project = db.query(EbookProject).filter(EbookProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content_items = (
        db.query(ContentItem)
        .filter(ContentItem.project_id == project_id)
        .order_by(ContentItem.chapter_order)
        .all()
    )
    if not content_items:
        raise HTTPException(status_code=400, detail="No content in project")

    dist = DistributionService(storage_service=storage)

    if export_type == "pages":
        gcs_path = dist.export_for_pages(project, content_items)
        return {"export_type": "pages", "format": "docx", "gcs_path": gcs_path}
    elif export_type == "canva":
        gcs_path = dist.export_for_canva(project, content_items)
        return {"export_type": "canva", "format": "json", "gcs_path": gcs_path}
    elif export_type == "audiobook":
        script = dist.prepare_audiobook_script(content_items)
        gcs_path = dist.generate_audiobook(
            project=project,
            text_content=script,
            language=project.language or "en",
        )
        return {"export_type": "audiobook", "format": "mp3", "gcs_path": gcs_path}
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown export type: {export_type}. Use: pages, canva, audiobook",
        )
