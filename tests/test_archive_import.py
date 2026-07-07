"""Tests for archive import functionality in database_dialog."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gallerydl_beyond.dialogs.database_dialog import (
    EXTRACTOR_URL_PATTERNS,
    _extract_galleries_from_archive,
    _get_gallerydl_categories,
    _parse_archive_entry,
    _reconstruct_url,
)


class TestParseArchiveEntry:
    """Test parsing of gallery-dl archive entries."""

    def test_parse_simple_format(self):
        """Parse entries like 'exhentai3617659_1'."""
        result = _parse_archive_entry("exhentai3617659_1")
        assert result == ("exhentai", "3617659", "1")

    def test_parse_with_page_suffix(self):
        """Parse entries with page numbers."""
        result = _parse_archive_entry("nhentai123456_5")
        assert result == ("nhentai", "123456", "5")

    def test_parse_pixiv_format(self):
        """Parse pixiv-style entries like 'pixiv12345678_p0'."""
        result = _parse_archive_entry("pixiv12345678_p0")
        assert result == ("pixiv", "12345678", "p0")

    def test_parse_no_page(self):
        """Parse entries without page suffix."""
        result = _parse_archive_entry("furaffinity98765432")
        assert result == ("furaffinity", "98765432", None)

    def test_parse_underscore_in_extractor(self):
        """Parse entries with underscore separator."""
        result = _parse_archive_entry("e621_12345_1")
        assert result is not None
        # Should extract some form of extractor and id

    def test_parse_danbooru_format(self):
        """Parse danbooru-style entries."""
        result = _parse_archive_entry("danbooru7654321_0")
        assert result == ("danbooru", "7654321", "0")

    def test_parse_gelbooru_format(self):
        """Parse gelbooru-style entries."""
        result = _parse_archive_entry("gelbooru9876543")
        assert result == ("gelbooru", "9876543", None)

    def test_parse_invalid_entry_returns_none(self):
        """Invalid entries should return None."""
        # Pure text, no numbers
        assert _parse_archive_entry("nodigitshere") is None

    def test_parse_empty_string(self):
        """Empty string should return None."""
        assert _parse_archive_entry("") is None

    def test_parse_multi_digit_page(self):
        """Parse entries with multi-digit page numbers."""
        result = _parse_archive_entry("hitomi1234567_123")
        assert result == ("hitomi", "1234567", "123")


class TestReconstructUrl:
    """Test URL reconstruction from extractor and gallery ID."""

    def test_reconstruct_pixiv(self):
        """Reconstruct pixiv URL."""
        url = _reconstruct_url("pixiv", "12345678")
        assert url == "https://www.pixiv.net/en/artworks/12345678"

    def test_reconstruct_danbooru(self):
        """Reconstruct danbooru URL."""
        url = _reconstruct_url("danbooru", "7654321")
        assert url == "https://danbooru.donmai.us/posts/7654321"

    def test_reconstruct_nhentai(self):
        """Reconstruct nhentai URL."""
        url = _reconstruct_url("nhentai", "123456")
        assert url == "https://nhentai.net/g/123456/"

    def test_reconstruct_twitter(self):
        """Reconstruct twitter URL."""
        url = _reconstruct_url("twitter", "1234567890123456789")
        assert url == "https://twitter.com/i/status/1234567890123456789"

    def test_reconstruct_e621(self):
        """Reconstruct e621 URL."""
        url = _reconstruct_url("e621", "3456789")
        assert url == "https://e621.net/posts/3456789"

    def test_reconstruct_furaffinity(self):
        """Reconstruct furaffinity URL."""
        url = _reconstruct_url("furaffinity", "12345678")
        assert url == "https://www.furaffinity.net/view/12345678"

    def test_reconstruct_gelbooru(self):
        """Reconstruct gelbooru URL."""
        url = _reconstruct_url("gelbooru", "9876543")
        assert url == "https://gelbooru.com/index.php?page=post&s=view&id=9876543"

    def test_reconstruct_case_insensitive(self):
        """Extractor name should be case-insensitive."""
        url1 = _reconstruct_url("PIXIV", "12345")
        url2 = _reconstruct_url("Pixiv", "12345")
        url3 = _reconstruct_url("pixiv", "12345")
        assert url1 == url2 == url3

    def test_reconstruct_exhentai_returns_none(self):
        """exhentai URLs cannot be reconstructed (need token)."""
        url = _reconstruct_url("exhentai", "3617659")
        assert url is None

    def test_reconstruct_unknown_extractor_returns_none(self):
        """Unknown extractors should return None."""
        url = _reconstruct_url("unknownsite", "12345")
        assert url is None

    def test_reconstruct_kemono(self):
        """Reconstruct kemono URL (has placeholder for service)."""
        url = _reconstruct_url("kemono", "12345")
        assert url is not None
        assert "kemono" in url

    def test_reconstruct_deviantart(self):
        """Reconstruct deviantart URL."""
        url = _reconstruct_url("deviantart", "987654321")
        assert url == "https://www.deviantart.com/deviation/987654321"


class TestExtractGalleriesFromArchive:
    """Test extraction of galleries from archive database."""

    @pytest.fixture
    def sample_archive(self, tmp_path: Path) -> Path:
        """Create a sample archive database."""
        archive_path = tmp_path / "archive.sqlite3"
        conn = sqlite3.connect(archive_path)
        conn.execute("CREATE TABLE archive (entry TEXT PRIMARY KEY) WITHOUT ROWID;")

        # Add sample entries
        entries = [
            "pixiv12345678_p0",
            "pixiv12345678_p1",
            "pixiv12345678_p2",
            "pixiv87654321_p0",
            "danbooru1111111",
            "danbooru2222222",
            "danbooru3333333",
            "exhentai9999999_1",
            "exhentai9999999_2",
            "exhentai9999999_3",
            "exhentai8888888_1",
        ]
        for entry in entries:
            conn.execute("INSERT INTO archive (entry) VALUES (?);", (entry,))
        conn.commit()
        conn.close()

        return archive_path

    def test_extract_galleries(self, sample_archive: Path):
        """Extract unique galleries from archive."""
        galleries = _extract_galleries_from_archive(sample_archive)

        assert "pixiv" in galleries
        assert "danbooru" in galleries
        assert "exhentai" in galleries

        # Check unique gallery IDs
        assert len(galleries["pixiv"]) == 2  # 12345678 and 87654321
        assert len(galleries["danbooru"]) == 3  # 1111111, 2222222, 3333333
        assert len(galleries["exhentai"]) == 2  # 9999999 and 8888888

    def test_extract_deduplicates_pages(self, sample_archive: Path):
        """Multiple pages from same gallery should count as one."""
        galleries = _extract_galleries_from_archive(sample_archive)

        # pixiv12345678 has 3 pages but should be 1 gallery
        assert "12345678" in galleries["pixiv"]
        assert "87654321" in galleries["pixiv"]
        assert len(galleries["pixiv"]) == 2

    def test_extract_empty_archive(self, tmp_path: Path):
        """Empty archive should return empty dict."""
        archive_path = tmp_path / "empty.sqlite3"
        conn = sqlite3.connect(archive_path)
        conn.execute("CREATE TABLE archive (entry TEXT PRIMARY KEY) WITHOUT ROWID;")
        conn.commit()
        conn.close()

        galleries = _extract_galleries_from_archive(archive_path)
        assert galleries == {}

    def test_extract_nonexistent_file(self, tmp_path: Path):
        """Non-existent file should return empty dict."""
        galleries = _extract_galleries_from_archive(tmp_path / "nonexistent.sqlite3")
        assert galleries == {}

    def test_extract_normalizes_extractor_names(self, sample_archive: Path):
        """Extractor names should be normalized (lowercase, stripped)."""
        galleries = _extract_galleries_from_archive(sample_archive)

        # All keys should be lowercase
        for extractor in galleries.keys():
            assert extractor == extractor.lower()


class TestGetGallerydlCategories:
    """Test runtime category loading from gallery-dl."""

    def test_get_categories_returns_dict(self):
        """Should return a dictionary."""
        categories = _get_gallerydl_categories()
        assert isinstance(categories, dict)

    def test_get_categories_has_known_sites(self):
        """Should include well-known sites if gallery-dl is installed."""
        categories = _get_gallerydl_categories()

        # These should exist if gallery-dl is installed
        if categories:  # Only test if we got results
            known_sites = ["pixiv", "twitter", "danbooru", "exhentai"]
            found = [site for site in known_sites if site in categories]
            assert len(found) > 0, "Expected to find at least one known site"

    def test_get_categories_values_are_strings(self):
        """Category values (roots) should be strings."""
        categories = _get_gallerydl_categories()

        for cat, root in categories.items():
            assert isinstance(cat, str)
            assert isinstance(root, str)


class TestExtractorUrlPatterns:
    """Test the EXTRACTOR_URL_PATTERNS dictionary."""

    def test_patterns_dict_exists(self):
        """EXTRACTOR_URL_PATTERNS should be a non-empty dict."""
        assert isinstance(EXTRACTOR_URL_PATTERNS, dict)
        assert len(EXTRACTOR_URL_PATTERNS) > 50  # We added ~90 patterns

    def test_patterns_have_id_placeholder(self):
        """URL patterns should contain {id} placeholder."""
        for extractor, pattern in EXTRACTOR_URL_PATTERNS.items():
            if pattern is not None:
                assert "{id}" in pattern, f"{extractor} pattern missing {{id}}: {pattern}"

    def test_patterns_none_for_complex_sites(self):
        """Complex sites that need tokens should have None pattern."""
        complex_sites = ["exhentai", "e-hentai", "discord"]
        for site in complex_sites:
            if site in EXTRACTOR_URL_PATTERNS:
                assert EXTRACTOR_URL_PATTERNS[site] is None, f"{site} should have None pattern"

    def test_patterns_have_valid_urls(self):
        """URL patterns should start with http(s)://."""
        for extractor, pattern in EXTRACTOR_URL_PATTERNS.items():
            if pattern is not None:
                assert pattern.startswith("http"), f"{extractor} pattern not a URL: {pattern}"

    def test_common_booru_sites_covered(self):
        """Common booru sites should have patterns."""
        booru_sites = ["danbooru", "gelbooru", "e621", "yandere", "konachan", "safebooru"]
        for site in booru_sites:
            assert site in EXTRACTOR_URL_PATTERNS, f"Missing booru site: {site}"
            assert EXTRACTOR_URL_PATTERNS[site] is not None, f"{site} should have pattern"

    def test_common_art_sites_covered(self):
        """Common art sites should have patterns."""
        art_sites = ["pixiv", "deviantart", "artstation", "furaffinity", "newgrounds"]
        for site in art_sites:
            assert site in EXTRACTOR_URL_PATTERNS, f"Missing art site: {site}"
            assert EXTRACTOR_URL_PATTERNS[site] is not None, f"{site} should have pattern"

    def test_common_social_sites_covered(self):
        """Common social media sites should have patterns."""
        social_sites = ["twitter", "instagram", "tumblr", "reddit"]
        for site in social_sites:
            assert site in EXTRACTOR_URL_PATTERNS, f"Missing social site: {site}"
            assert EXTRACTOR_URL_PATTERNS[site] is not None, f"{site} should have pattern"
