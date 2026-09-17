import pytest
from backend.app.processors.hasher import compute_content_hash


def test_content_hash_deterministic():
    """Hash output must be identical for identical input payloads."""
    h1 = compute_content_hash(
        title="Global Trade Accord",
        url="https://example.com/item/1",
        description="Leaders sign agreement.",
    )
    h2 = compute_content_hash(
        title="Global Trade Accord",
        url="https://example.com/item/1",
        description="Leaders sign agreement.",
    )
    assert h1 == h2
    assert len(h1) == 64  # Valid SHA-256 hex string


def test_content_hash_case_and_whitespace_invariant():
    """Hash should normalize leading/trailing whitespace and casing for robustness."""
    h1 = compute_content_hash(
        title="  Global Trade Accord  ",
        url="https://EXAMPLE.COM/item/1",
        description="Leaders sign agreement.",
    )
    h2 = compute_content_hash(
        title="global trade accord",
        url="https://example.com/item/1",
        description="Leaders sign agreement.",
    )
    assert h1 == h2


def test_content_hash_differentiates_distinct_content():
    """Different stories must yield distinct hashes."""
    h1 = compute_content_hash(
        title="Summit in Geneva",
        url="https://example.com/geneva",
        description="Peace talks resume.",
    )
    h2 = compute_content_hash(
        title="Port Congestion Relieved",
        url="https://example.com/port",
        description="Cargo flow resumes.",
    )
    assert h1 != h2
