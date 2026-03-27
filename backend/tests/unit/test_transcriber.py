"""
Unit tests for the YouTube transcript extraction module.
"""

import pytest
from app.ingestion.transcriber import extract_youtube_id


class TestExtractYouTubeId:
    def test_full_url(self):
        assert extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert extract_youtube_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_bare_id(self):
        assert extract_youtube_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_url_with_extra_params(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120s&list=PLtest"
        assert extract_youtube_id(url) == "dQw4w9WgXcQ"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Could not extract"):
            extract_youtube_id("https://example.com/not-a-video")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            extract_youtube_id("")
