import re
from typing import Optional, Any, Dict
from datetime import datetime
from backend.app.schemas.document import NormalizedDocument
from backend.app.processors.hasher import compute_content_hash
from backend.app.utils.time import parse_datetime_utc, utc_now

# Regex for stripping HTML tags
_TAG_RE = re.compile(r"<[^>]+>")
# Regex for collapsing multiple whitespace characters
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html_tags(text: Optional[str]) -> str:
    """Remove HTML tags cleanly without leaving spurious whitespace before punctuation."""
    if not text:
        return ""
    # Replace block-level tags with a space
    clean = re.sub(r"</?(?:p|div|br|hr|h[1-6]|li|tr|ul|ol)[^>]*>", " ", text, flags=re.IGNORECASE)
    # Strip remaining inline tags
    clean = re.sub(r"<[^>]+>", "", clean)
    # Eliminate spaces preceding punctuation marks
    clean = re.sub(r"\s+([,.:;?!])", r"\1", clean)
    return _WHITESPACE_RE.sub(" ", clean).strip()


def clean_text(text: Optional[str]) -> Optional[str]:
    """Clean and normalize whitespace in text, returning None if empty."""
    if not text:
        return None
    cleaned = strip_html_tags(text)
    return cleaned if cleaned else None


def build_normalized_document(
    source_name: str,
    title: str,
    url: str,
    published_at: Optional[Any] = None,
    external_id: Optional[str] = None,
    description: Optional[str] = None,
    content: Optional[str] = None,
    content_format: str = "text/plain",
    author: Optional[str] = None,
    language: str = "en",
    raw_metadata: Optional[Dict[str, Any]] = None,
) -> NormalizedDocument:
    """Transform raw extracted source elements into a validated NormalizedDocument."""
    norm_title = clean_text(title) or "Untitled"
    norm_url = (url or "").strip()
    norm_desc = clean_text(description)
    norm_content = clean_text(content)
    norm_author = clean_text(author)
    
    # Handle published_at timestamp
    if published_at is not None:
        try:
            norm_published_at = parse_datetime_utc(published_at)
        except Exception:
            norm_published_at = utc_now()
    else:
        norm_published_at = utc_now()

    # Compute content hash
    content_hash = compute_content_hash(
        title=norm_title,
        url=norm_url,
        content=norm_content,
        description=norm_desc,
    )

    return NormalizedDocument(
        source_name=source_name,
        external_id=str(external_id).strip() if external_id is not None else None,
        title=norm_title,
        description=norm_desc,
        content=norm_content,
        content_format=content_format,
        url=norm_url,
        author=norm_author,
        published_at=norm_published_at,
        language=language.lower()[:16] if language else "en",
        raw_metadata=raw_metadata or {},
        content_hash=content_hash,
    )
