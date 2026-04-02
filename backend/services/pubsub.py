"""Google Cloud Pub/Sub service for event-driven content processing."""

import json

from google.cloud import pubsub_v1

from config.settings import settings


class PubSubService:
    """Publishes and subscribes to Pub/Sub topics for async processing."""

    def __init__(self):
        self.publisher = pubsub_v1.PublisherClient()
        self.project_path = f"projects/{settings.gcp_project_id}"

    def _topic_path(self, topic_name: str) -> str:
        return self.publisher.topic_path(settings.gcp_project_id, topic_name)

    def publish_content_ingested(self, project_id: str, content_item_id: str, content_type: str):
        """Publish event when new content is uploaded and ready for AI processing."""
        topic = self._topic_path(settings.pubsub_ingestion_topic)
        message = {
            "event": "content_ingested",
            "project_id": project_id,
            "content_item_id": content_item_id,
            "content_type": content_type,
        }
        self.publisher.publish(topic, json.dumps(message).encode("utf-8"))

    def publish_content_processed(self, project_id: str, content_item_id: str):
        """Publish event when content has been processed by AI."""
        topic = self._topic_path(settings.pubsub_processing_topic)
        message = {
            "event": "content_processed",
            "project_id": project_id,
            "content_item_id": content_item_id,
        }
        self.publisher.publish(topic, json.dumps(message).encode("utf-8"))

    def publish_ebook_ready(self, project_id: str, ebook_file_id: str, format: str):
        """Publish event when an ebook has been generated."""
        topic = self._topic_path(settings.pubsub_ebook_ready_topic)
        message = {
            "event": "ebook_ready",
            "project_id": project_id,
            "ebook_file_id": ebook_file_id,
            "format": format,
        }
        self.publisher.publish(topic, json.dumps(message).encode("utf-8"))
