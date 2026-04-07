"""Tests for the platform formatter — 2026 publishing specs."""

from backend.services.platform_formatter import Platform, PlatformFormatter


class TestPlatformSpecs:
    """Verify all major platforms are defined with 2026 specs."""

    def setup_method(self):
        self.formatter = PlatformFormatter()

    def test_all_platforms_defined(self):
        platforms = self.formatter.get_all_platforms()
        names = [p["platform"] for p in platforms]
        assert "amazon_kdp" in names
        assert "apple_books" in names
        assert "google_play" in names
        assert "kobo" in names
        assert "barnes_noble" in names
        assert "draft2digital" in names
        assert "ingram_spark" in names

    def test_amazon_kdp_supports_epub(self):
        spec = self.formatter.get_platform_spec(Platform.AMAZON_KDP)
        assert "epub" in spec.supported_formats

    def test_apple_books_requires_isbn(self):
        spec = self.formatter.get_platform_spec(Platform.APPLE_BOOKS)
        assert spec.metadata_fields["isbn"]["required"] is True

    def test_apple_books_epub_only(self):
        spec = self.formatter.get_platform_spec(Platform.APPLE_BOOKS)
        assert spec.supported_formats == ["epub"]

    def test_kdp_cover_specs(self):
        spec = self.formatter.get_platform_spec(Platform.AMAZON_KDP)
        assert spec.cover_image_specs["recommended_width"] == 2560
        assert spec.cover_image_specs["dpi"] == 300


class TestPlatformValidation:
    """Test validation logic against platform requirements."""

    def setup_method(self):
        self.formatter = PlatformFormatter()

    def test_valid_epub_for_kdp(self):
        result = self.formatter.validate_for_platform(
            platform=Platform.AMAZON_KDP,
            ebook_format="epub",
            file_size_bytes=5 * 1024 * 1024,  # 5MB
            metadata={
                "title": "Test Book",
                "author": "Test Author",
                "description": "A test book",
                "language": "en",
                "categories": ["Education"],
            },
            has_toc=True,
            has_cover=True,
            cover_width=2560,
            images_have_alt_text=True,
        )
        assert result.is_valid is True
        assert result.format_ready is True

    def test_invalid_format_for_apple(self):
        result = self.formatter.validate_for_platform(
            platform=Platform.APPLE_BOOKS,
            ebook_format="pdf",
            file_size_bytes=1024,
            metadata={"title": "Test"},
            has_toc=True,
            has_cover=True,
        )
        assert result.is_valid is False
        assert any(i.field == "format" for i in result.issues)

    def test_missing_isbn_for_apple(self):
        result = self.formatter.validate_for_platform(
            platform=Platform.APPLE_BOOKS,
            ebook_format="epub",
            file_size_bytes=1024,
            metadata={
                "title": "Test",
                "author": "Author",
                "description": "Desc",
                "publisher": "Pub",
                "language": "en",
                "categories": ["Education"],
                # No ISBN
            },
            has_toc=True,
            has_cover=True,
        )
        assert any(i.field == "isbn" for i in result.issues)

    def test_file_too_large(self):
        result = self.formatter.validate_for_platform(
            platform=Platform.KOBO,
            ebook_format="epub",
            file_size_bytes=500 * 1024 * 1024,  # 500MB, Kobo limit is 400MB
            metadata={
                "title": "Test",
                "author": "Author",
                "description": "Desc",
                "isbn": "978-0-1234-5678-9",
                "language": "en",
                "categories": ["Education"],
            },
            has_toc=True,
            has_cover=True,
        )
        assert result.is_valid is False
        assert any(i.field == "file_size" for i in result.issues)

    def test_missing_cover(self):
        result = self.formatter.validate_for_platform(
            platform=Platform.AMAZON_KDP,
            ebook_format="epub",
            file_size_bytes=1024,
            metadata={
                "title": "Test",
                "author": "Author",
                "description": "Desc",
                "language": "en",
                "categories": ["Education"],
            },
            has_toc=True,
            has_cover=False,
        )
        assert any(i.field == "cover" for i in result.issues)

    def test_alt_text_error_for_apple(self):
        result = self.formatter.validate_for_platform(
            platform=Platform.APPLE_BOOKS,
            ebook_format="epub",
            file_size_bytes=1024,
            metadata={
                "title": "Test",
                "author": "Author",
                "description": "Desc",
                "publisher": "Pub",
                "language": "en",
                "isbn": "978-0-1234-5678-9",
                "categories": ["Education"],
            },
            has_toc=True,
            has_cover=True,
            images_have_alt_text=False,
        )
        # Apple requires alt text (error), others just warn
        alt_issues = [i for i in result.issues if i.field == "accessibility"]
        assert len(alt_issues) == 1
        assert alt_issues[0].severity == "error"

    def test_validate_all_platforms(self):
        results = self.formatter.validate_for_all_platforms(
            ebook_format="epub",
            file_size_bytes=10 * 1024 * 1024,
            metadata={
                "title": "Universal Test Book",
                "author": "Author",
                "description": "A test book for all platforms",
                "language": "en",
                "isbn": "978-0-1234-5678-9",
                "publisher": "Test Publisher",
                "categories": ["Education"],
            },
            has_toc=True,
            has_cover=True,
            cover_width=2560,
            cover_height=1600,
            images_have_alt_text=True,
        )
        assert len(results) == 7  # All platforms
        # EPUB should pass for most platforms
        assert results["amazon_kdp"].format_ready is True
        assert results["apple_books"].format_ready is True
