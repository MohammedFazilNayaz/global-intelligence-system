import uuid
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from backend.app.extractors.rules import RuleBasedIntelligenceExtractor
from backend.app.schemas.extraction import ExtractionResult, ExtractionProvenance


def test_rule_based_extractor_entities_and_events():
    """Verify RuleBasedIntelligenceExtractor extracts entities, events, roles, and scores."""
    extractor = RuleBasedIntelligenceExtractor()
    doc_id = uuid.uuid4()
    now = datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone.utc)

    title = "Federal Reserve Holds Rates Steady Amid China Trade Pact Talks"
    desc = "The central bank in Washington maintained its benchmark rate as officials in Beijing announced tariff cuts."
    content = "Detailed report from the United States Treasury discussing crude oil prices and euro currency fluctuations."

    result = extractor.extract(
        document_id=doc_id,
        title=title,
        description=desc,
        content=content,
        published_at=now,
    )

    assert isinstance(result, ExtractionResult)
    assert isinstance(result.metadata, ExtractionProvenance)
    assert result.metadata.extractor_name == "RuleBasedIntelligenceExtractor"

    # Entities check
    canonical_names = {e.canonical_name for e in result.entities}
    assert "Federal Reserve" in canonical_names
    assert "China" in canonical_names
    assert "Washington, D.C." in canonical_names
    assert "Beijing" in canonical_names
    assert "United States" in canonical_names
    assert "Crude Oil" in canonical_names
    assert "Euro" in canonical_names

    # Check title entities receive high confidence
    fed_mention = next(e for e in result.entities if e.canonical_name == "Federal Reserve")
    assert fed_mention.confidence >= 0.90
    assert fed_mention.role == "actor"

    # Events check
    event_types = {ev.event_type for ev in result.events}
    assert "central_bank_decision" in event_types
    assert "trade_action" in event_types

    cb_event = next(ev for ev in result.events if ev.event_type == "central_bank_decision")
    assert cb_event.confidence > 0.0
    assert cb_event.importance > 0.0
    assert cb_event.confidence != cb_event.importance


def test_rule_based_extractor_provenance():
    """Verify extraction provenance metadata is properly stamped."""
    extractor = RuleBasedIntelligenceExtractor(version="0.2.0")
    result = extractor.extract(
        document_id=uuid.uuid4(),
        title="Diplomats Meet in Geneva",
    )
    assert result.metadata.extractor_name == "RuleBasedIntelligenceExtractor"
    assert result.metadata.extractor_version == "0.2.0"
    assert result.metadata.processed_at.tzinfo is not None


def test_extraction_result_contract_validation():
    """Verify Pydantic strictly validates ExtractionResult and rejects invalid scores or missing metadata."""
    valid_prov = ExtractionProvenance(
        extractor_name="TestExtractor",
        extractor_version="1.0.0",
        processed_at=datetime.now(timezone.utc),
    )

    # Invalid confidence > 1.0
    with pytest.raises(ValidationError):
        ExtractionResult(
            entities=[
                {
                    "entity_type": "COUNTRY",
                    "canonical_name": "France",
                    "normalized_name": "france",
                    "mention_text": "France",
                    "confidence": 1.5,  # Invalid
                }
            ],
            events=[],
            metadata=valid_prov,
        )

    # Invalid importance < 0.0
    with pytest.raises(ValidationError):
        ExtractionResult(
            entities=[],
            events=[
                {
                    "event_type": "conflict",
                    "title": "Border Skirmish",
                    "confidence": 0.8,
                    "importance": -0.2,  # Invalid
                }
            ],
            metadata=valid_prov,
        )
