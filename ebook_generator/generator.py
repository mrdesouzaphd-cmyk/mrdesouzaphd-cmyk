"""Ebook generator — creates EPUB and PDF from processed content.

Supports:
- EPUB 3.0 with accessibility metadata
- PDF via WeasyPrint (CSS-based layout)
- Bilingual templates (EN/PT-BR)
- UDL-compliant structure
- Image optimization and alt-text
- Video content represented as rich text sections
"""

import uuid
from datetime import datetime, timezone
from io import BytesIO

from ebooklib import epub
from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.services.storage import StorageService


class EbookGenerator:
    """Generates EPUB and PDF ebooks from structured content."""

    def __init__(self, storage_service: StorageService):
        self.storage = storage_service
        self.jinja_env = Environment(
            loader=FileSystemLoader("ebook_generator/templates"),
            autoescape=select_autoescape(["html"]),
        )

    def generate(self, project, content_items, output_format: str = "epub") -> tuple[bytes, str]:
        """Generate an ebook in the specified format.

        Args:
            project: EbookProject database model
            content_items: list of ContentItem database models, ordered by chapter_order
            output_format: "epub" or "pdf"

        Returns:
            tuple of (file_bytes, filename)
        """
        if output_format == "epub":
            return self._generate_epub(project, content_items)
        elif output_format == "pdf":
            return self._generate_pdf(project, content_items)
        else:
            raise ValueError(f"Unsupported format: {output_format}")

    def _generate_epub(self, project, content_items) -> tuple[bytes, str]:
        """Generate an EPUB 3.0 ebook with accessibility metadata."""
        book = epub.EpubBook()

        # Metadata
        book_id = str(uuid.uuid4())
        book.set_identifier(book_id)
        book.set_title(project.title)
        book.set_language(project.language or "en")
        book.add_author("DrDeSouzAI Content Agent")

        if project.description:
            book.add_metadata("DC", "description", project.description)

        # Accessibility metadata (EPUB 3.0 / UDL)
        book.add_metadata(
            None, "meta", "long description",
            {"property": "schema:accessibilitySummary"},
        )
        book.add_metadata(
            None, "meta", "textual, visual",
            {"property": "schema:accessMode"},
        )
        book.add_metadata(
            None, "meta", "textual",
            {"property": "schema:accessModeSufficient"},
        )

        # Default CSS
        style = self._get_default_css()
        css_item = epub.EpubItem(
            uid="style",
            file_name="style/default.css",
            media_type="text/css",
            content=style.encode("utf-8"),
        )
        book.add_item(css_item)

        # Build chapters
        chapters = []
        image_items = []

        for i, item in enumerate(content_items):
            chapter_title = item.title or f"Chapter {i + 1}"

            if item.content_type == "text":
                html_content = self._render_text_chapter(
                    title=chapter_title,
                    text=item.raw_text or "",
                    language=project.language,
                )
            elif item.content_type == "image":
                html_content, img_item = self._render_image_chapter(
                    title=chapter_title,
                    item=item,
                    chapter_index=i,
                )
                if img_item:
                    image_items.append(img_item)
                    book.add_item(img_item)
            elif item.content_type == "video":
                html_content = self._render_video_chapter(
                    title=chapter_title,
                    item=item,
                )
            else:
                continue

            chapter = epub.EpubHtml(
                title=chapter_title,
                file_name=f"chapter_{i + 1}.xhtml",
                lang=project.language or "en",
            )
            chapter.content = html_content
            chapter.add_item(css_item)
            book.add_item(chapter)
            chapters.append(chapter)

        # Table of contents
        book.toc = chapters

        # Navigation
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Spine
        book.spine = ["nav"] + chapters

        # Write to bytes
        buffer = BytesIO()
        epub.write_epub(buffer, book)
        filename = f"{self._slugify(project.title)}.epub"
        return buffer.getvalue(), filename

    def _generate_pdf(self, project, content_items) -> tuple[bytes, str]:
        """Generate a PDF ebook using WeasyPrint."""
        from weasyprint import HTML

        template = self.jinja_env.get_template("pdf_template.html")

        chapters_data = []
        for i, item in enumerate(content_items):
            chapter = {
                "title": item.title or f"Chapter {i + 1}",
                "content_type": item.content_type,
                "text": item.raw_text or "",
                "ai_description": item.ai_description or "",
                "ai_caption": item.ai_caption or "",
            }

            if item.content_type == "image" and item.gcs_processed_path:
                try:
                    img_data = self.storage.download_file(item.gcs_processed_path)
                    import base64
                    chapter["image_base64"] = base64.b64encode(img_data).decode()
                except Exception:
                    chapter["image_base64"] = None
            else:
                chapter["image_base64"] = None

            chapters_data.append(chapter)

        html_content = template.render(
            title=project.title,
            description=project.description or "",
            language=project.language or "en",
            chapters=chapters_data,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )

        pdf_bytes = HTML(string=html_content).write_pdf()
        filename = f"{self._slugify(project.title)}.pdf"
        return pdf_bytes, filename

    def _render_text_chapter(self, title: str, text: str, language: str) -> str:
        """Render a text chapter as XHTML."""
        # Convert plain text paragraphs to HTML
        paragraphs = text.strip().split("\n\n")
        html_paragraphs = "\n".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())

        return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="{language}">
<head><title>{title}</title></head>
<body>
<h1>{title}</h1>
{html_paragraphs}
</body>
</html>"""

    def _render_image_chapter(self, title: str, item, chapter_index: int):
        """Render an image chapter as XHTML with the image embedded."""
        img_item = None
        img_tag = ""

        if item.gcs_processed_path or item.gcs_raw_path:
            path = item.gcs_processed_path or item.gcs_raw_path
            try:
                img_data = self.storage.download_file(path)
                img_filename = f"image_{chapter_index}.jpg"
                img_item = epub.EpubItem(
                    uid=f"img_{chapter_index}",
                    file_name=f"images/{img_filename}",
                    media_type="image/jpeg",
                    content=img_data,
                )
                alt_text = item.ai_description or title
                img_tag = (
                    f'<figure>'
                    f'<img src="images/{img_filename}" alt="{alt_text}" />'
                    f'<figcaption>{item.ai_caption or title}</figcaption>'
                    f'</figure>'
                )
            except Exception:
                img_tag = f"<p><em>[Image could not be loaded: {title}]</em></p>"

        description = item.ai_description or ""
        caption = item.ai_caption or ""

        html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{title}</title></head>
<body>
<h1>{title}</h1>
{img_tag}
{"<p>" + description + "</p>" if description else ""}
</body>
</html>"""

        return html, img_item

    def _render_video_chapter(self, title: str, item) -> str:
        """Render a video chapter as a text summary section."""
        description = item.ai_description or "Video content summary not yet available."
        caption = item.ai_caption or ""

        return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{title}</title></head>
<body>
<h1>{title}</h1>
<div class="video-summary">
<p class="video-indicator"><strong>Video Content</strong></p>
<p>{description}</p>
{"<p><em>" + caption + "</em></p>" if caption else ""}
</div>
</body>
</html>"""

    def _get_default_css(self) -> str:
        """Return default CSS for the ebook — minimalist, futuristic aesthetic."""
        return """
/* Content-to-Ebook Agent — Minimalist Futuristic Theme */
@charset "utf-8";

body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    line-height: 1.8;
    color: #1a1a2e;
    margin: 2em;
    max-width: 40em;
}

h1 {
    font-weight: 300;
    font-size: 2em;
    letter-spacing: 0.02em;
    border-bottom: 2px solid #0f3460;
    padding-bottom: 0.3em;
    margin-bottom: 1.2em;
    color: #0f3460;
}

h2 {
    font-weight: 400;
    font-size: 1.4em;
    color: #16213e;
    margin-top: 1.5em;
}

p {
    text-align: justify;
    margin-bottom: 1em;
    font-size: 1em;
}

figure {
    margin: 1.5em 0;
    text-align: center;
}

figure img {
    max-width: 100%;
    height: auto;
    border-radius: 4px;
}

figcaption {
    font-size: 0.85em;
    color: #555;
    font-style: italic;
    margin-top: 0.5em;
}

.video-summary {
    background: #f8f9fa;
    border-left: 4px solid #0f3460;
    padding: 1em 1.5em;
    margin: 1.5em 0;
    border-radius: 0 4px 4px 0;
}

.video-indicator {
    color: #0f3460;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.8em;
}

blockquote {
    border-left: 3px solid #e94560;
    padding-left: 1em;
    color: #333;
    font-style: italic;
    margin: 1.5em 0;
}

.udl-prompt {
    background: #eef2ff;
    padding: 1em;
    border-radius: 4px;
    margin: 1em 0;
    font-size: 0.95em;
}

.udl-prompt::before {
    content: "Reflect: ";
    font-weight: 600;
    color: #0f3460;
}
"""

    def _slugify(self, text: str) -> str:
        """Convert text to a URL-safe slug."""
        import re
        slug = text.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug[:80]
