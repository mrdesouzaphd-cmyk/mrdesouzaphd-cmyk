"""Video processing for ebook content using Video Intelligence AI."""

from google.cloud import videointelligence


class VideoProcessor:
    """Process videos for ebook integration.

    Since videos cannot be directly embedded in EPUB/PDF, this processor
    extracts key information to represent the video as rich text content
    in the ebook, with optional QR code links to the original video.
    """

    def __init__(self):
        self.client = videointelligence.VideoIntelligenceServiceClient()

    def analyze_video(self, video_uri: str) -> dict:
        """Analyze a video from GCS using Video Intelligence AI.

        Extracts:
        - Labels (content categories)
        - Shot changes (scene boundaries)
        - Text (OCR from video frames)
        - Speech transcription
        """
        features = [
            videointelligence.Feature.LABEL_DETECTION,
            videointelligence.Feature.SHOT_CHANGE_DETECTION,
            videointelligence.Feature.TEXT_DETECTION,
            videointelligence.Feature.SPEECH_TRANSCRIPTION,
        ]

        # Configure speech transcription
        speech_config = videointelligence.SpeechTranscriptionConfig(
            language_code="en-US",
            enable_automatic_punctuation=True,
            # Also try Portuguese
            alternative_language_codes=["pt-BR"],
        )
        video_context = videointelligence.VideoContext(
            speech_transcription_config=speech_config,
        )

        operation = self.client.annotate_video(
            request={
                "input_uri": video_uri,
                "features": features,
                "video_context": video_context,
            }
        )

        result = operation.result(timeout=600)
        annotation = result.annotation_results[0]

        return {
            "labels": self._extract_labels(annotation),
            "shots": self._extract_shots(annotation),
            "text": self._extract_text(annotation),
            "transcript": self._extract_transcript(annotation),
        }

    def _extract_labels(self, annotation) -> list[dict]:
        """Extract video-level labels."""
        labels = []
        for label in annotation.segment_label_annotations:
            for segment in label.segments:
                labels.append({
                    "description": label.entity.description,
                    "confidence": segment.confidence,
                })
        return sorted(labels, key=lambda x: x["confidence"], reverse=True)[:15]

    def _extract_shots(self, annotation) -> list[dict]:
        """Extract shot/scene boundaries."""
        shots = []
        for i, shot in enumerate(annotation.shot_annotations):
            start = shot.start_time_offset.total_seconds()
            end = shot.end_time_offset.total_seconds()
            shots.append({
                "shot_number": i + 1,
                "start_seconds": start,
                "end_seconds": end,
                "duration_seconds": end - start,
            })
        return shots

    def _extract_text(self, annotation) -> list[str]:
        """Extract on-screen text via OCR."""
        texts = set()
        for text_annotation in annotation.text_annotations:
            texts.add(text_annotation.text)
        return list(texts)

    def _extract_transcript(self, annotation) -> str:
        """Extract speech transcription."""
        transcript_parts = []
        for speech in annotation.speech_transcriptions:
            for alternative in speech.alternatives:
                if alternative.confidence > 0.5:
                    transcript_parts.append(alternative.transcript)
        return " ".join(transcript_parts)

    def create_ebook_representation(self, analysis: dict, video_url: str = "") -> dict:
        """Create rich text representation of video for ebook inclusion.

        Returns structured content that the ebook generator can render
        as a chapter section with video summary, key points, and optional
        link to the original video.
        """
        transcript = analysis.get("transcript", "")
        labels = analysis.get("labels", [])
        on_screen_text = analysis.get("text", [])
        shots = analysis.get("shots", [])

        # Build narrative description
        label_names = [l["description"] for l in labels[:5]]
        topic_summary = ", ".join(label_names) if label_names else "various topics"

        sections = {
            "title": f"Video Content: {topic_summary.title()}",
            "description": (
                f"This section summarizes video content covering {topic_summary}. "
                f"The video contains {len(shots)} distinct scenes."
            ),
            "transcript_excerpt": transcript[:2000] if transcript else None,
            "on_screen_text": on_screen_text[:10] if on_screen_text else None,
            "key_topics": label_names,
            "video_link": video_url if video_url else None,
            "scene_count": len(shots),
        }

        return sections
