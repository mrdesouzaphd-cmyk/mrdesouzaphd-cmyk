"""Platform-specific ebook formatting for major distribution channels.

Each platform has specific requirements for file format, metadata,
cover images, and content structure. This module ensures the ebook
agent produces output that passes validation on:

- Amazon Kindle Direct Publishing (KDP)
- Apple Books (via Apple Books for Authors / iTunes Connect)
- Google Play Books
- Kobo Writing Life
- Barnes & Noble Press (Nook)
- Smashwords / Draft2Digital (aggregators)
- IngramSpark (print + digital distribution)

2026 format requirements are tracked and enforced.
"""

import json
import structlog
from dataclasses import dataclass, field
from enum import Enum

logger = structlog.get_logger()


class Platform(str, Enum):
    AMAZON_KDP = "amazon_kdp"
    APPLE_BOOKS = "apple_books"
    GOOGLE_PLAY = "google_play"
    KOBO = "kobo"
    BARNES_NOBLE = "barnes_noble"
    SMASHWORDS = "smashwords"
    DRAFT2DIGITAL = "draft2digital"
    INGRAM_SPARK = "ingram_spark"


@dataclass
class PlatformSpec:
    """Specification for a publishing platform's requirements."""

    platform: Platform
    supported_formats: list[str]
    max_file_size_mb: int
    cover_image_specs: dict
    metadata_fields: dict
    content_requirements: list[str]
    drm_options: list[str]
    pricing_currency: list[str]
    notes: str = ""


# ──────────────────────────────────────────────────────────────
# 2026 Platform Specifications
# ──────────────────────────────────────────────────────────────

PLATFORM_SPECS: dict[Platform, PlatformSpec] = {
    Platform.AMAZON_KDP: PlatformSpec(
        platform=Platform.AMAZON_KDP,
        supported_formats=["epub", "kpf", "docx", "pdf"],
        max_file_size_mb=650,
        cover_image_specs={
            "min_width": 1000,
            "min_height": 1600,
            "recommended_width": 2560,
            "recommended_height": 1600,
            "max_file_size_mb": 50,
            "formats": ["jpg", "tiff"],
            "aspect_ratio": "1:1.6",
            "dpi": 300,
        },
        metadata_fields={
            "title": {"required": True, "max_chars": 200},
            "subtitle": {"required": False, "max_chars": 200},
            "author": {"required": True},
            "description": {"required": True, "max_chars": 4000},
            "keywords": {"required": False, "max_count": 7},
            "categories": {"required": True, "max_count": 3},
            "language": {"required": True},
            "isbn": {"required": False},
            "series_name": {"required": False},
            "edition": {"required": False},
        },
        content_requirements=[
            "EPUB 3.0 or EPUB 2.0.1 supported",
            "Reflowable layout preferred for text-heavy books",
            "Fixed-layout for image-heavy or children's books",
            "Table of Contents (TOC) required — both NCX and HTML nav",
            "Images: JPEG or PNG, max 5MB per image",
            "No DRM watermarks in source file",
            "Internal links must use relative paths",
            "CSS must not reference external resources",
            "Font embedding supported but optional",
            "Alt text required for all images (accessibility)",
        ],
        drm_options=["kindle_drm", "none"],
        pricing_currency=["USD", "GBP", "EUR", "BRL", "JPY"],
        notes="KDP uses proprietary KF8/AZW3 format internally. EPUB is converted on upload.",
    ),

    Platform.APPLE_BOOKS: PlatformSpec(
        platform=Platform.APPLE_BOOKS,
        supported_formats=["epub"],
        max_file_size_mb=2000,
        cover_image_specs={
            "min_short_side": 1400,
            "max_long_side": 3200,
            "formats": ["jpg", "png"],
            "color_space": "RGB",
            "dpi": 300,
        },
        metadata_fields={
            "title": {"required": True},
            "author": {"required": True},
            "description": {"required": True, "max_chars": 4000},
            "publisher": {"required": True},
            "language": {"required": True},
            "isbn": {"required": True, "note": "ISBN required for Apple Books"},
            "categories": {"required": True},
            "page_count": {"required": False},
            "series_info": {"required": False},
        },
        content_requirements=[
            "EPUB 3.0 strongly preferred (EPUB 2 accepted but limited features)",
            "Must pass EpubCheck validation with zero errors",
            "Cover image embedded in EPUB + separate file for store listing",
            "Table of Contents required (HTML nav element)",
            "Accessibility metadata required (WCAG 2.1 AA)",
            "Alt text mandatory for all images",
            "Font embedding supported (OpenType/TrueType)",
            "Audio/video embedding supported in EPUB 3.0",
            "iBooks-specific CSS extensions available for enhanced layout",
            "Multi-touch book features via Pages export or iBooks Author",
            "Apple requires 'Made with Pages' or standard EPUB",
        ],
        drm_options=["fairplay_drm", "none"],
        pricing_currency=["USD", "BRL", "EUR", "GBP"],
        notes=(
            "Apple Books supports EPUB 3.0 with media overlays for audiobook sync. "
            "Books can be submitted via Apple Books for Authors or Pages direct publish. "
            "ISBN is mandatory for paid books."
        ),
    ),

    Platform.GOOGLE_PLAY: PlatformSpec(
        platform=Platform.GOOGLE_PLAY,
        supported_formats=["epub", "pdf"],
        max_file_size_mb=2000,
        cover_image_specs={
            "min_width": 640,
            "min_height": 1024,
            "recommended_width": 2560,
            "recommended_height": 1600,
            "formats": ["jpg", "png", "tiff"],
        },
        metadata_fields={
            "title": {"required": True},
            "author": {"required": True},
            "description": {"required": True},
            "isbn": {"required": False},
            "language": {"required": True},
            "categories": {"required": True},
        },
        content_requirements=[
            "EPUB 3.0 or PDF supported",
            "PDF must have embedded fonts",
            "TOC required",
            "Alt text for images recommended",
        ],
        drm_options=["google_drm", "none"],
        pricing_currency=["USD", "BRL", "EUR"],
    ),

    Platform.KOBO: PlatformSpec(
        platform=Platform.KOBO,
        supported_formats=["epub"],
        max_file_size_mb=400,
        cover_image_specs={
            "recommended_width": 1600,
            "recommended_height": 2400,
            "formats": ["jpg", "png"],
        },
        metadata_fields={
            "title": {"required": True},
            "author": {"required": True},
            "description": {"required": True, "max_chars": 5000},
            "isbn": {"required": True},
            "language": {"required": True},
            "categories": {"required": True},
        },
        content_requirements=[
            "EPUB 3.0 preferred",
            "Must pass EpubCheck",
            "TOC required",
            "Accessibility metadata encouraged",
        ],
        drm_options=["kobo_drm", "none"],
        pricing_currency=["USD", "CAD", "GBP", "EUR", "BRL"],
    ),

    Platform.BARNES_NOBLE: PlatformSpec(
        platform=Platform.BARNES_NOBLE,
        supported_formats=["epub", "docx"],
        max_file_size_mb=650,
        cover_image_specs={
            "min_width": 1400,
            "min_height": 1400,
            "recommended_width": 2500,
            "formats": ["jpg", "png"],
        },
        metadata_fields={
            "title": {"required": True},
            "author": {"required": True},
            "description": {"required": True},
            "isbn": {"required": False},
            "categories": {"required": True},
        },
        content_requirements=[
            "EPUB 2 or EPUB 3 supported",
            "Must pass EpubCheck",
            "TOC required",
        ],
        drm_options=["bn_drm", "none"],
        pricing_currency=["USD", "GBP"],
    ),

    Platform.DRAFT2DIGITAL: PlatformSpec(
        platform=Platform.DRAFT2DIGITAL,
        supported_formats=["epub", "docx", "rtf", "pdf"],
        max_file_size_mb=300,
        cover_image_specs={
            "recommended_width": 2560,
            "recommended_height": 1600,
            "formats": ["jpg", "png"],
        },
        metadata_fields={
            "title": {"required": True},
            "author": {"required": True},
            "description": {"required": True},
            "isbn": {"required": False, "note": "Free ISBN provided by D2D"},
            "categories": {"required": True},
        },
        content_requirements=[
            "EPUB 3.0 preferred",
            "Distributes to 20+ retailers automatically",
            "Handles format conversion internally",
            "TOC auto-generated from headings",
        ],
        drm_options=["optional"],
        pricing_currency=["USD"],
        notes="Draft2Digital is an aggregator — distributes to Apple, Kobo, B&N, and more.",
    ),

    Platform.INGRAM_SPARK: PlatformSpec(
        platform=Platform.INGRAM_SPARK,
        supported_formats=["epub", "pdf"],
        max_file_size_mb=650,
        cover_image_specs={
            "print_cover": {
                "format": "pdf",
                "bleed": "0.125in",
                "spine_calculated": True,
            },
            "ebook_cover": {
                "min_width": 1600,
                "formats": ["jpg"],
            },
        },
        metadata_fields={
            "title": {"required": True},
            "author": {"required": True},
            "isbn": {"required": True, "note": "Separate ISBNs for print and ebook"},
            "description": {"required": True},
            "bisac_codes": {"required": True, "max_count": 3},
        },
        content_requirements=[
            "Print: PDF/X-1a or PDF/X-3 with embedded fonts",
            "Ebook: EPUB 3.0 preferred",
            "Print cover requires spine width calculation",
            "Global distribution to 40,000+ retailers and libraries",
        ],
        drm_options=["adobe_drm", "none"],
        pricing_currency=["USD", "GBP", "EUR", "AUD", "CAD"],
        notes="IngramSpark handles both print-on-demand and ebook distribution globally.",
    ),
}


@dataclass
class ValidationIssue:
    severity: str  # "error", "warning", "info"
    field: str
    message: str


@dataclass
class PlatformValidationResult:
    platform: Platform
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    metadata_ready: bool = False
    format_ready: bool = False


class PlatformFormatter:
    """Validates and formats ebooks for specific publishing platforms."""

    def get_platform_spec(self, platform: Platform) -> PlatformSpec:
        """Get the specification for a given platform."""
        return PLATFORM_SPECS[platform]

    def get_all_platforms(self) -> list[dict]:
        """List all supported platforms with their key specs."""
        return [
            {
                "platform": spec.platform.value,
                "formats": spec.supported_formats,
                "requires_isbn": spec.metadata_fields.get("isbn", {}).get("required", False),
                "max_file_size_mb": spec.max_file_size_mb,
                "notes": spec.notes,
            }
            for spec in PLATFORM_SPECS.values()
        ]

    def validate_for_platform(
        self,
        platform: Platform,
        ebook_format: str,
        file_size_bytes: int,
        metadata: dict,
        has_toc: bool = True,
        has_cover: bool = False,
        cover_width: int = 0,
        cover_height: int = 0,
        images_have_alt_text: bool = True,
    ) -> PlatformValidationResult:
        """Validate an ebook against a platform's requirements.

        Returns a detailed validation result with any issues found.
        """
        spec = PLATFORM_SPECS[platform]
        issues = []

        # Format check
        if ebook_format not in spec.supported_formats:
            issues.append(ValidationIssue(
                severity="error",
                field="format",
                message=(
                    f"{platform.value} does not support '{ebook_format}'. "
                    f"Supported: {spec.supported_formats}"
                ),
            ))

        # File size check
        file_size_mb = file_size_bytes / (1024 * 1024)
        if file_size_mb > spec.max_file_size_mb:
            issues.append(ValidationIssue(
                severity="error",
                field="file_size",
                message=f"File size {file_size_mb:.1f}MB exceeds {platform.value} limit of {spec.max_file_size_mb}MB",
            ))

        # Required metadata
        for field_name, field_spec in spec.metadata_fields.items():
            if field_spec.get("required") and not metadata.get(field_name):
                issues.append(ValidationIssue(
                    severity="error",
                    field=field_name,
                    message=f"'{field_name}' is required for {platform.value}",
                ))

            # Check character limits
            max_chars = field_spec.get("max_chars")
            if max_chars and metadata.get(field_name):
                if len(str(metadata[field_name])) > max_chars:
                    issues.append(ValidationIssue(
                        severity="warning",
                        field=field_name,
                        message=f"'{field_name}' exceeds {max_chars} character limit for {platform.value}",
                    ))

        # Cover image
        if not has_cover:
            issues.append(ValidationIssue(
                severity="error",
                field="cover",
                message=f"Cover image is required for {platform.value}",
            ))
        elif cover_width > 0:
            min_w = spec.cover_image_specs.get("min_width", spec.cover_image_specs.get("min_short_side", 0))
            if min_w and cover_width < min_w:
                issues.append(ValidationIssue(
                    severity="warning",
                    field="cover",
                    message=f"Cover width {cover_width}px is below recommended {min_w}px for {platform.value}",
                ))

        # TOC
        if not has_toc:
            issues.append(ValidationIssue(
                severity="error",
                field="toc",
                message=f"Table of Contents is required for {platform.value}",
            ))

        # Accessibility (especially important for Apple Books)
        if not images_have_alt_text:
            severity = "error" if platform == Platform.APPLE_BOOKS else "warning"
            issues.append(ValidationIssue(
                severity=severity,
                field="accessibility",
                message=f"Alt text for images is {'required' if severity == 'error' else 'recommended'} for {platform.value}",
            ))

        is_valid = not any(i.severity == "error" for i in issues)

        return PlatformValidationResult(
            platform=platform,
            is_valid=is_valid,
            issues=issues,
            metadata_ready=not any(
                i.severity == "error" and i.field in spec.metadata_fields
                for i in issues
            ),
            format_ready=not any(
                i.severity == "error" and i.field in ("format", "file_size")
                for i in issues
            ),
        )

    def validate_for_all_platforms(
        self, ebook_format: str, file_size_bytes: int, metadata: dict, **kwargs
    ) -> dict[str, PlatformValidationResult]:
        """Validate an ebook against all supported platforms at once."""
        results = {}
        for platform in Platform:
            results[platform.value] = self.validate_for_platform(
                platform=platform,
                ebook_format=ebook_format,
                file_size_bytes=file_size_bytes,
                metadata=metadata,
                **kwargs,
            )
        return results

    def get_apple_books_specific_css(self) -> str:
        """Return Apple Books-specific CSS enhancements.

        Apple Books supports iBooks CSS extensions for enhanced layout
        on iPad/iPhone/Mac.
        """
        return """
/* Apple Books-specific enhancements */
/* These properties are prefixed with -ibooks- and only apply in Apple Books */

body {
    /* Enable hyphenation for better text flow */
    -webkit-hyphens: auto;
    hyphens: auto;
}

/* Full-bleed images on Apple Books */
figure.full-bleed {
    -ibooks-layout-hint: full-screen-spread;
    margin: 0;
    padding: 0;
}

/* Interactive elements */
aside.pullquote {
    -ibooks-popover: popup;
    border: 1px solid #ccc;
    padding: 1em;
    cursor: pointer;
}

/* Night mode support */
@media (prefers-color-scheme: dark) {
    body {
        background-color: #1a1a1a;
        color: #e0e0e0;
    }

    h1, h2, h3 {
        color: #7eb8da;
    }

    .video-summary {
        background: #2a2a2a;
        border-left-color: #7eb8da;
    }
}
"""

    def generate_apple_pages_export_guide(self) -> str:
        """Instructions for publishing via Apple Pages to Apple Books."""
        return """
# Publishing to Apple Books via Apple Pages

## Direct Publishing from Pages
Apple Pages can publish directly to Apple Books:

1. Open your DOCX export in Apple Pages
2. Apply your preferred Pages template
3. Go to File > Publish to Apple Books
4. Fill in metadata (title, author, description, categories)
5. Set pricing and territories
6. Submit for review

## Requirements for Pages-to-Apple Books
- Apple ID with Apple Books for Authors account
- ISBN (required for paid books — get one from Bowker or your national ISBN agency)
- Cover image: min 1400px on shortest side, JPG or PNG, RGB color space
- Content must pass Apple's review guidelines
- No links to competing ebook stores

## Tips for Best Results
- Use Pages' built-in styles (Heading 1, Heading 2, Body) for automatic TOC generation
- Insert images using Insert > Image (not drag-and-drop) for better control
- Use Pages' accessibility features to add alt text to all images
- Preview your book using the Pages ebook preview before publishing
- Pages automatically generates EPUB 3.0 output

## Multi-language Support
- Set the document language in Format > Language & Region
- Pages supports both English and Portuguese (Brazilian) typography
"""
