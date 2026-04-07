"""Image processing for ebook content using Cloud Vision AI and Pillow."""

from io import BytesIO

from google.cloud import vision
from PIL import Image


class ImageProcessor:
    """Process and optimize images for ebook inclusion."""

    def __init__(self):
        self.vision_client = vision.ImageAnnotatorClient()

    def analyze_image(self, image_bytes: bytes) -> dict:
        """Analyze an image using Cloud Vision AI.

        Returns labels, text (OCR), and safe-search annotations.
        """
        image = vision.Image(content=image_bytes)

        # Run multiple detections in parallel
        features = [
            vision.Feature(type_=vision.Feature.Type.LABEL_DETECTION, max_results=10),
            vision.Feature(type_=vision.Feature.Type.TEXT_DETECTION),
            vision.Feature(type_=vision.Feature.Type.SAFE_SEARCH_DETECTION),
            vision.Feature(type_=vision.Feature.Type.IMAGE_PROPERTIES),
        ]

        request = vision.AnnotateImageRequest(image=image, features=features)
        response = self.vision_client.annotate_image(request=request)

        labels = [
            {"description": label.description, "score": label.score}
            for label in response.label_annotations
        ]

        ocr_text = ""
        if response.text_annotations:
            ocr_text = response.text_annotations[0].description

        safe_search = response.safe_search_annotation
        safety = {
            "adult": safe_search.adult.name if safe_search else "UNKNOWN",
            "violence": safe_search.violence.name if safe_search else "UNKNOWN",
        }

        return {
            "labels": labels,
            "ocr_text": ocr_text,
            "safety": safety,
        }

    def optimize_for_ebook(
        self,
        image_bytes: bytes,
        max_width: int = 1200,
        max_height: int = 1600,
        quality: int = 85,
        output_format: str = "JPEG",
    ) -> bytes:
        """Resize and compress an image for ebook format.

        Maintains aspect ratio while fitting within max dimensions.
        Converts to RGB if necessary (e.g., RGBA PNGs).
        """
        img = Image.open(BytesIO(image_bytes))

        # Convert RGBA to RGB for JPEG output
        if img.mode in ("RGBA", "P") and output_format == "JPEG":
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[3])
            img = background

        # Resize maintaining aspect ratio
        img.thumbnail((max_width, max_height), Image.LANCZOS)

        buffer = BytesIO()
        img.save(buffer, format=output_format, quality=quality, optimize=True)
        return buffer.getvalue()

    def generate_alt_text(self, analysis: dict) -> str:
        """Generate accessible alt-text from Vision AI analysis.

        Creates a human-readable description suitable for screen readers
        and UDL compliance.
        """
        labels = analysis.get("labels", [])
        ocr_text = analysis.get("ocr_text", "")

        if not labels:
            return "Image content could not be analyzed."

        top_labels = [l["description"] for l in labels[:5]]
        description = f"Image showing {', '.join(top_labels[:-1])}"
        if len(top_labels) > 1:
            description += f" and {top_labels[-1]}"
        else:
            description += top_labels[0] if top_labels else ""

        if ocr_text.strip():
            first_line = ocr_text.strip().split("\n")[0][:100]
            description += f'. Contains text: "{first_line}"'

        return description + "."
