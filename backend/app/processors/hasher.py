import hashlib
from typing import Optional


def compute_content_hash(
    title: str,
    url: str,
    content: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """Compute a deterministic SHA-256 content hash for deduplication.
    
    Combines canonical URL, normalized title, and content body (or description).
    """
    clean_title = (title or "").strip().lower()
    clean_url = (url or "").strip().lower()
    body = (content or description or "").strip()
    
    # Take the first 1000 characters of body for content fingerprinting
    # to avoid minor trailing dynamic artifacts while capturing the core story
    body_snippet = body[:1000].lower()
    
    payload = f"{clean_url}|{clean_title}|{body_snippet}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
