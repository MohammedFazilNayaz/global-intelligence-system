from datetime import datetime, timezone
import pytest
from backend.app.processors.normalizer import (
    strip_html_tags,
    clean_text,
    build_normalized_document,
)
from backend.app.schemas.document import NormalizedDocument


def test_strip_html_tags():
    raw_html = "<p>Emergency meeting declared at <b>UN headquarters</b>.</p>"
    result = strip_html_tags(raw_html)
    assert result == "Emergency meeting declared at UN headquarters."


def test_clean_text():
    assert clean_text("   Lots of    spaces \n and tabs  ") == "Lots of spaces and tabs"
    assert clean_text("") is None
    assert clean_text(None) is None


def test_build_normalized_document():
    doc = build_normalized_document(
        source_name="Global Wire",
        title="<p>Trade Treaty Finalized</p>",
        url="https://example.com/treaty",
        published_at="2026-09-07T14:30:00Z",
        external_id="ext-999",
        description="Negotiators completed the text.",
        content="<p>Full text of treaty negotiation...</p>",
        author="Diplomatic Editor",
        language="EN-US",
        raw_metadata={"raw_key": 123},
    )

    assert isinstance(doc, NormalizedDocument)
    assert doc.source_name == "Global Wire"
    assert doc.title == "Trade Treaty Finalized"
    assert doc.url == "https://example.com/treaty"
    assert doc.published_at.tzinfo == timezone.utc
    assert doc.published_at.year == 2026
    assert doc.author == "Diplomatic Editor"
    assert doc.language == "en-us"
    assert len(doc.content_hash) == 64
    assert doc.raw_metadata == {"raw_key": 123}
