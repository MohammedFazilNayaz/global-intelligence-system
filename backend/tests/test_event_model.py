import uuid
from datetime import datetime, timezone
import pytest
from backend.app.models.event import ExtractedEvent
from backend.app.models.entity import Entity
from backend.app.schemas.extraction import EventType, EntityType


def test_extracted_event_model_creation(db_session, sample_document):
    """Verify ExtractedEvent creation, UUID primary key, and distinct confidence/importance scores."""
    now = datetime(2026, 9, 7, 14, 30, 0, tzinfo=timezone.utc)
    event = ExtractedEvent(
        document_id=sample_document.id,
        event_type=EventType.CENTRAL_BANK_DECISION.value,
        event_title="Federal Reserve Holds Benchmark Rates Steady",
        event_summary="Policymakers maintained the target range citing balanced risks.",
        event_time=now,
        confidence=0.92,
        importance=0.85,
        metadata_={"trigger": "holds rates", "source": "RuleBasedIntelligenceExtractor"},
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    assert isinstance(event.id, uuid.UUID)
    assert event.event_type == "central_bank_decision"
    assert event.confidence == 0.92
    assert event.importance == 0.85
    assert event.confidence != event.importance  # Verify distinctly tracked
    assert event.created_at.tzinfo == timezone.utc
    assert event.event_time == now


def test_extracted_event_location_entity_relationship(db_session, sample_document):
    """Verify location_entity relationship and SET NULL behavior upon entity deletion."""
    loc = Entity(
        entity_type=EntityType.CITY.value,
        canonical_name="Washington, D.C.",
        normalized_name="washington d.c.",
        country_code="US",
    )
    db_session.add(loc)
    db_session.commit()

    event = ExtractedEvent(
        document_id=sample_document.id,
        event_type=EventType.GOVERNMENT_DECISION.value,
        event_title="White House Issues Executive Order on Cross-Border Data Flow",
        location_entity_id=loc.id,
        confidence=0.88,
        importance=0.72,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    assert event.location_entity is not None
    assert event.location_entity.canonical_name == "Washington, D.C."

    # Deleting location entity should set location_entity_id to NULL, not delete the event
    db_session.delete(loc)
    db_session.commit()
    db_session.expire_all()
    db_session.refresh(event)

    assert event.location_entity_id is None


def test_extracted_event_cascade_on_document_delete(db_session, sample_document):
    """Verify extracted events are deleted when parent document is deleted."""
    event = ExtractedEvent(
        document_id=sample_document.id,
        event_type=EventType.TRADE_ACTION.value,
        event_title="Corridor Tariff Agreement Signed",
        confidence=0.89,
        importance=0.80,
    )
    db_session.add(event)
    db_session.commit()

    event_id = event.id
    db_session.delete(sample_document)
    db_session.commit()

    assert db_session.get(ExtractedEvent, event_id) is None
