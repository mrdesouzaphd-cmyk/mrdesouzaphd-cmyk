"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings backed by env vars and Secret Manager."""

    # GCP
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"
    gcs_raw_bucket: str = ""
    gcs_processed_bucket: str = ""
    gcs_ebook_bucket: str = ""

    # Pub/Sub
    pubsub_ingestion_topic: str = "content-ingestion"
    pubsub_processing_topic: str = "content-processing"
    pubsub_ebook_ready_topic: str = "ebook-ready"

    # Database (Cloud SQL - PostgreSQL)
    database_url: str = ""

    # Vertex AI
    vertex_ai_location: str = "us-central1"

    # Application
    app_name: str = "Content-to-Ebook Agent"
    app_version: str = "0.1.0"
    debug: bool = False
    allowed_origins: list[str] = ["*"]

    # Upload limits
    max_upload_size_mb: int = 500
    allowed_image_types: list[str] = ["image/jpeg", "image/png", "image/webp", "image/gif"]
    allowed_video_types: list[str] = ["video/mp4", "video/webm", "video/quicktime"]

    model_config = {"env_prefix": "EBOOK_AGENT_", "env_file": ".env"}


settings = Settings()
