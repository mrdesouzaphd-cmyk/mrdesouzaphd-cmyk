"""External tool integrations — Claude AI, HeyGen, and local workflow helpers.

Manages connections to:
- Claude AI (via Anthropic API) for advanced content enhancement
- HeyGen (video generation from text/avatar)
- Local file sync (Claude Coworker workflow)
"""

import json
import structlog

from config.settings import settings

logger = structlog.get_logger()


class ClaudeAIIntegration:
    """Use Claude AI for advanced content refinement.

    Claude excels at:
    - Maintaining human voice while improving clarity
    - Scientific writing with narrative flow
    - Bilingual content (EN/PT-BR) with cultural nuance
    - Detecting subtle bias patterns
    """

    def __init__(self, api_key: str | None = None):
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
            self.available = True
        except (ImportError, Exception):
            self.client = None
            self.available = False
            logger.warning("claude_ai_not_available")

    def refine_for_ebook(self, text: str, language: str = "en") -> str:
        """Refine text content for ebook quality using Claude.

        Preserves the author's voice while improving:
        - Clarity and flow
        - Scientific rigor
        - Narrative engagement
        - UDL-friendly structure
        """
        if not self.available:
            return text

        lang_name = "English" if language == "en" else "Brazilian Portuguese"

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": (
                    f"You are a professional ebook editor. Refine this {lang_name} text "
                    f"for a professional ebook publication.\n\n"
                    f"RULES:\n"
                    f"- Preserve the author's unique voice and intent\n"
                    f"- Improve clarity, flow, and engagement\n"
                    f"- Maintain scientific accuracy and tone\n"
                    f"- Ensure narrative progression (not bullet-point style)\n"
                    f"- Add natural transitions between ideas\n"
                    f"- Do NOT make it sound AI-generated\n"
                    f"- Keep the language as {lang_name}\n"
                    f"- Return ONLY the refined text, nothing else\n\n"
                    f"TEXT:\n{text}"
                ),
            }],
        )

        return message.content[0].text

    def generate_ebook_metadata(self, title: str, description: str, language: str = "en") -> dict:
        """Generate SEO-optimized metadata for ebook distribution platforms.

        Creates keywords, categories, and enhanced description for:
        - Amazon KDP
        - Gumroad
        - Other platforms
        """
        if not self.available:
            return {
                "keywords": [],
                "categories": [],
                "enhanced_description": description,
            }

        lang_name = "English" if language == "en" else "Brazilian Portuguese"

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": (
                    f"Generate ebook marketplace metadata for this book:\n"
                    f"Title: {title}\n"
                    f"Description: {description}\n"
                    f"Language: {lang_name}\n\n"
                    f"Return JSON with:\n"
                    f'- "keywords": list of 7 SEO keywords\n'
                    f'- "categories": list of 3 marketplace categories\n'
                    f'- "enhanced_description": a compelling 2-paragraph description '
                    f"for the sales page (in {lang_name})\n"
                    f'- "target_audience": who this book is for\n'
                ),
            }],
        )

        try:
            text = message.content[0].text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass

        return {
            "keywords": [],
            "categories": [],
            "enhanced_description": description,
        }


class HeyGenIntegration:
    """Integration with HeyGen for AI video generation.

    HeyGen can create professional videos from text scripts using
    AI avatars. This integration allows:
    - Generating promotional videos for ebook marketing
    - Creating video summaries of ebook chapters
    - Producing companion video content
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self.base_url = "https://api.heygen.com"
        self.available = api_key is not None

    async def create_video_from_script(
        self,
        script: str,
        avatar_id: str = "default",
        voice_id: str | None = None,
        language: str = "en",
    ) -> dict:
        """Generate a video using HeyGen's API from a text script.

        This could be used to create:
        - Book trailer / promotional video
        - Chapter summary videos
        - Educational companion videos
        """
        if not self.available:
            return {
                "status": "unavailable",
                "message": "HeyGen API key not configured. Set EBOOK_AGENT_HEYGEN_API_KEY.",
            }

        import httpx

        payload = {
            "video_inputs": [{
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                },
                "voice": {
                    "type": "text",
                    "input_text": script,
                    "voice_id": voice_id or ("en-US-default" if language == "en" else "pt-BR-default"),
                },
            }],
            "dimension": {"width": 1920, "height": 1080},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v2/video/generate",
                json=payload,
                headers={
                    "X-Api-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                logger.info("heygen_video_created", video_id=data.get("data", {}).get("video_id"))
                return {
                    "status": "processing",
                    "video_id": data.get("data", {}).get("video_id"),
                    "message": "Video is being generated. Check status with the video_id.",
                }
            else:
                logger.error("heygen_error", status=response.status_code, body=response.text)
                return {
                    "status": "error",
                    "message": f"HeyGen API error: {response.status_code}",
                }


class LocalWorkflowHelper:
    """Helpers for local workflow integration with Claude Coworker/Code.

    Generates scripts and instructions for setting up:
    - Local folder monitoring (auto-upload to GCS)
    - Claude Coworker automation
    - CapCut/Adobe Express asset preparation guidelines
    """

    @staticmethod
    def generate_upload_script(bucket_name: str, project_id: str) -> str:
        """Generate a bash script for local file upload to GCS.

        Users can run this script from their local machine to
        automatically sync a local folder to their GCS project bucket.
        """
        return f"""#!/bin/bash
# Content-to-Ebook Agent — Local Upload Script
# Syncs a local folder to your GCS project bucket.
#
# Usage:
#   ./upload_content.sh /path/to/your/content/folder
#
# Prerequisites:
#   - Google Cloud SDK installed (gcloud)
#   - Authenticated: gcloud auth login
#   - Project set: gcloud config set project YOUR_PROJECT_ID

LOCAL_DIR="${{1:-.}}"
BUCKET="gs://{bucket_name}/projects/{project_id}"

echo "Uploading content from $LOCAL_DIR to $BUCKET ..."

# Upload text files
gsutil -m cp "$LOCAL_DIR"/*.txt "$LOCAL_DIR"/*.md "$LOCAL_DIR"/*.docx "$BUCKET/text/" 2>/dev/null

# Upload images
gsutil -m cp "$LOCAL_DIR"/*.jpg "$LOCAL_DIR"/*.jpeg "$LOCAL_DIR"/*.png "$LOCAL_DIR"/*.webp "$BUCKET/images/" 2>/dev/null

# Upload videos
gsutil -m cp "$LOCAL_DIR"/*.mp4 "$LOCAL_DIR"/*.webm "$LOCAL_DIR"/*.mov "$BUCKET/videos/" 2>/dev/null

echo "Upload complete! Your content will be processed automatically."
"""

    @staticmethod
    def generate_coworker_instructions() -> str:
        """Generate instructions for setting up Claude Coworker integration."""
        return """
# Claude Coworker Integration — Content-to-Ebook Agent

## Setup
1. Install Claude Coworker on your desktop
2. Create a dedicated folder: ~/ebook-content/
3. Configure Coworker to watch this folder

## Workflow
1. Drop your files into ~/ebook-content/{project-name}/
   - Text: .txt, .md, .docx files
   - Images: .jpg, .png, .webp (from Adobe Express or CapCut exports)
   - Videos: .mp4, .webm (from HeyGen or CapCut exports)

2. Coworker detects new files and uploads them to Google Cloud Storage

3. The upload triggers the processing pipeline automatically

4. You receive a notification when your ebook is ready

## Tips
- Use CapCut to trim and optimize videos before uploading
- Export Adobe Express designs as high-res PNG/JPG
- HeyGen videos should be exported as MP4
- Apple Pages: export chapters as DOCX for best compatibility
"""
