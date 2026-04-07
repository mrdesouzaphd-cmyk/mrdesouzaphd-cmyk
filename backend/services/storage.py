"""Google Cloud Storage service for uploading and retrieving content."""

import io
import uuid
from pathlib import PurePosixPath

from google.cloud import storage

from config.settings import settings


class StorageService:
    """Manages file uploads/downloads to Google Cloud Storage."""

    def __init__(self):
        self.client = storage.Client(project=settings.gcp_project_id)

    def _get_bucket(self, bucket_name: str) -> storage.Bucket:
        return self.client.bucket(bucket_name)

    def upload_raw_content(
        self,
        project_id: str,
        file_data: bytes,
        filename: str,
        content_type: str,
    ) -> str:
        """Upload raw content (image/video) to the raw bucket.

        Returns the GCS path (gs://bucket/path).
        """
        bucket = self._get_bucket(settings.gcs_raw_bucket)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        blob_path = str(PurePosixPath("projects", project_id, unique_name))
        blob = bucket.blob(blob_path)
        blob.upload_from_string(file_data, content_type=content_type)
        return f"gs://{settings.gcs_raw_bucket}/{blob_path}"

    def upload_processed_content(
        self,
        project_id: str,
        file_data: bytes,
        filename: str,
        content_type: str,
    ) -> str:
        """Upload processed content to the processed bucket."""
        bucket = self._get_bucket(settings.gcs_processed_bucket)
        blob_path = str(PurePosixPath("projects", project_id, filename))
        blob = bucket.blob(blob_path)
        blob.upload_from_string(file_data, content_type=content_type)
        return f"gs://{settings.gcs_processed_bucket}/{blob_path}"

    def upload_ebook(
        self,
        project_id: str,
        file_data: bytes,
        filename: str,
        content_type: str,
    ) -> str:
        """Upload generated ebook to the ebook bucket."""
        bucket = self._get_bucket(settings.gcs_ebook_bucket)
        blob_path = str(PurePosixPath("projects", project_id, filename))
        blob = bucket.blob(blob_path)
        blob.upload_from_string(file_data, content_type=content_type)
        return f"gs://{settings.gcs_ebook_bucket}/{blob_path}"

    def download_file(self, gcs_path: str) -> bytes:
        """Download a file from GCS given a gs:// path."""
        # Parse gs://bucket/path
        parts = gcs_path.replace("gs://", "").split("/", 1)
        bucket_name, blob_path = parts[0], parts[1]
        bucket = self._get_bucket(bucket_name)
        blob = bucket.blob(blob_path)
        return blob.download_as_bytes()

    def generate_signed_url(self, gcs_path: str, expiration_minutes: int = 60) -> str:
        """Generate a signed URL for temporary access to a file."""
        import datetime

        parts = gcs_path.replace("gs://", "").split("/", 1)
        bucket_name, blob_path = parts[0], parts[1]
        bucket = self._get_bucket(bucket_name)
        blob = bucket.blob(blob_path)
        return blob.generate_signed_url(
            expiration=datetime.timedelta(minutes=expiration_minutes),
            method="GET",
        )

    def list_project_files(self, bucket_name: str, project_id: str) -> list[str]:
        """List all files for a project in a bucket."""
        bucket = self._get_bucket(bucket_name)
        prefix = f"projects/{project_id}/"
        blobs = bucket.list_blobs(prefix=prefix)
        return [f"gs://{bucket_name}/{blob.name}" for blob in blobs]
