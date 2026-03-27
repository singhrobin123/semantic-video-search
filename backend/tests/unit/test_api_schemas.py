"""
Unit tests for API schema validation.

Ensures Pydantic models enforce constraints and the API envelope
always has a predictable shape.
"""

import pytest
from pydantic import ValidationError

from app.api.schemas import APIEnvelope, SearchRequest, IngestYouTubeRequest


class TestSearchRequest:
    def test_valid_query(self):
        req = SearchRequest(query="What is database scaling?")
        assert req.query == "What is database scaling?"

    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="   ")


class TestAPIEnvelope:
    def test_success_envelope(self):
        env = APIEnvelope(success=True, data={"results": []})
        assert env.success is True
        assert env.error is None

    def test_error_envelope(self):
        env = APIEnvelope(success=False, error="Something went wrong")
        assert env.success is False
        assert env.data is None

    def test_serialization_shape(self):
        env = APIEnvelope(success=True, data={"key": "value"})
        d = env.model_dump()
        assert set(d.keys()) == {"success", "data", "error"}


class TestIngestYouTubeRequest:
    def test_defaults(self):
        req = IngestYouTubeRequest(url="https://youtube.com/watch?v=abc123abc12")
        assert req.languages == ["en"]
