import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select

from backend.app.clustering.similarity import (
    tokenize_and_normalize,
    jaccard_similarity,
    temporal_proximity_score,
    location_similarity_score,
)
from backend.app.clustering.scorer import (
    calculate_cluster_match,
    ClusterMatchScore,
    DEFAULT_CLUSTER_THRESHOLD,
    WEIGHT_EVENT_TYPE,
    WEIGHT_TEMPORAL,
    WEIGHT_LOCATION,
    WEIGHT_ACTOR,
    WEIGHT_ENTITY,
    WEIGHT_LEXICAL,
)
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.models.document import Document
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.event import ExtractedEvent
from backend.app.services.clustering_service import (
    cluster_extracted_event,
    cluster_document_events,
    update_cluster_aggregate_state,
    get_cluster_for_event,
    get_event_cluster,
)
from backend.app.processors.hasher import compute_content_hash


def test_weights_sum_to_one():
    """Verify calibrated scoring weights sum exactly to 1.00."""
    total_weights = (
        WEIGHT_EVENT_TYPE
        + WEIGHT_TEMPORAL
        + WEIGHT_LOCATION
        + WEIGHT_ACTOR
        + WEIGHT_ENTITY
        + WEIGHT_LEXICAL
    )
    assert round(total_weights, 4) == 1.00


def test_tokenize_and_normalize():
    """Verify lexical tokenization, stopword removal, and punctuation stripping."""
    text = "The Federal Reserve raised interest rates by 25 basis points in Washington!"
    tokens = tokenize_and_normalize(text)
    assert "federal" in tokens
    assert "reserve" in tokens
    assert "rates" in tokens
    assert "basis" in tokens
    assert "points" in tokens
    # Stopwords removed
    assert "the" not in tokens
    assert "by" not in tokens
    assert "in" not in tokens


def test_temporal_proximity_score():
    """Verify temporal exponential decay and 48-hour cutoff."""
    t0 = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
    t_1h = t0 + timedelta(hours=1)
    t_24h = t0 + timedelta(hours=24)
    t_49h = t0 + timedelta(hours=49)

    score_0 = temporal_proximity_score(t0, t0)
    assert score_0 == 1.0

    score_1h = temporal_proximity_score(t0, t_1h)
    assert score_1h > 0.95

    score_24h = temporal_proximity_score(t0, t_24h)
    assert 0.35 < score_24h < 0.40

    score_49h = temporal_proximity_score(t0, t_49h)
    assert score_49h == 0.0, "Time difference > 48h must be hard-cut to 0.0"

    score_none = temporal_proximity_score(t0, None)
    assert score_none == 0.5


def test_location_similarity_score():
    """Verify location matching, hierarchical compatibility, and country veto."""
    loc_id1 = uuid.uuid4()
    loc_id2 = uuid.uuid4()

    # Same location ID
    score, veto = location_similarity_score(loc_id1, loc_id1)
    assert score == 1.0 and not veto

    # Both None (neutral)
    score, veto = location_similarity_score(None, None)
    assert score == 0.7 and not veto

    # Same country (e.g. City Kyiv in Country Ukraine)
    score, veto = location_similarity_score(loc_id1, loc_id2, country_a="UA", country_b="UA")
    assert score == 0.9 and not veto

    # Conflicting sovereign countries (e.g. Japan vs Ukraine) -> VETO
    score, veto = location_similarity_score(loc_id1, loc_id2, country_a="JP", country_b="UA")
    assert score == 0.0 and veto


def test_calculate_cluster_match_veto_event_type():
    """Verify mismatched event types immediately veto clustering."""
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    score = calculate_cluster_match(
        event_type_a="conflict",
        event_type_b="central_bank_decision",
        time_a=now,
        time_b=now,
        loc_a_id=None,
        loc_b_id=None,
    )
    assert score.is_vetoed
    assert not score.is_match
    assert score.final_score == 0.0
    assert score.veto_reason == "event_type_mismatch"


def test_calculate_cluster_match_positive_merge():
    """Verify closely matching reports produce high composite score exceeding threshold."""
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    t_15m = now + timedelta(minutes=15)
    loc_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    score = calculate_cluster_match(
        event_type_a="central_bank_decision",
        event_type_b="central_bank_decision",
        time_a=now,
        time_b=t_15m,
        loc_a_id=loc_id,
        loc_b_id=loc_id,
        country_a="US",
        country_b="US",
        actor_ids_a={actor_id},
        actor_ids_b={actor_id},
        all_entity_ids_a={actor_id, loc_id},
        all_entity_ids_b={actor_id, loc_id},
        text_a="Federal Reserve Raises Benchmark Interest Rates by 25 Basis Points",
        text_b="Fed Increases Benchmark Rate Amid Moderating Inflation",
    )
    assert not score.is_vetoed
    assert score.is_match
    assert score.final_score >= DEFAULT_CLUSTER_THRESHOLD
    meta = score.to_metadata_dict()
    assert meta["event_type_score"] == 1.0
    assert meta["temporal_score"] > 0.95
    assert meta["location_score"] == 1.0
    assert meta["actor_overlap_score"] == 1.0


def test_cluster_extracted_event_service(db_session, sample_source):
    """Test full clustering lifecycle: first event creates cluster, second attaches, third distinct creates new."""
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)

    # Create canonical ECB actor
    ecb_entity = Entity(
        entity_type="CENTRAL_BANK",
        canonical_name="European Central Bank",
        normalized_name="european central bank",
        metadata_={},
    )
    db_session.add(ecb_entity)
    db_session.flush()

    # Document 1: ECB rate hike
    doc1 = Document(
        source_id=sample_source.id,
        title="ECB Raises Rates by 25 Basis Points",
        url="https://example.com/ecb/1",
        published_at=now,
        content_hash=compute_content_hash("ECB 1", "url1"),
        processing_status="NORMALIZED",
    )
    db_session.add(doc1)
    db_session.flush()

    db_session.add(DocumentEntity(
        document_id=doc1.id,
        entity_id=ecb_entity.id,
        mention_text="ECB",
        entity_role="actor",
        confidence=0.95,
        metadata_={},
    ))

    ev1 = ExtractedEvent(
        document_id=doc1.id,
        event_type="central_bank_decision",
        event_title="ECB Raises Rates by 25 Basis Points",
        event_time=now,
        confidence=0.95,
        importance=0.90,
    )
    db_session.add(ev1)
    db_session.commit()

    # Cluster Event 1 -> Should create founding cluster
    mem1 = cluster_extracted_event(db_session, ev1.id)
    assert mem1.membership_score == 1.0
    cluster1 = db_session.get(EventCluster, mem1.event_cluster_id)
    assert cluster1 is not None
    assert cluster1.canonical_title == ev1.event_title
    assert cluster1.event_type == "central_bank_decision"
    assert cluster1.metadata_["document_count"] == 1

    # Document 2: Corroborating ECB report 1 hour later
    doc2 = Document(
        source_id=sample_source.id,
        title="European Central Bank Increases Benchmark Rates",
        url="https://example.com/ecb/2",
        published_at=now + timedelta(hours=1),
        content_hash=compute_content_hash("ECB 2", "url2"),
        processing_status="NORMALIZED",
    )
    db_session.add(doc2)
    db_session.flush()

    db_session.add(DocumentEntity(
        document_id=doc2.id,
        entity_id=ecb_entity.id,
        mention_text="European Central Bank",
        entity_role="actor",
        confidence=0.96,
        metadata_={},
    ))

    ev2 = ExtractedEvent(
        document_id=doc2.id,
        event_type="central_bank_decision",
        event_title="European Central Bank Increases Benchmark Rates by Quarter Point",
        event_time=now + timedelta(hours=1),
        confidence=0.96,
        importance=0.90,
    )
    db_session.add(ev2)
    db_session.commit()

    # Cluster Event 2 -> Should match and merge into cluster1
    mem2 = cluster_extracted_event(db_session, ev2.id)
    assert mem2.event_cluster_id == cluster1.id
    assert mem2.membership_score >= DEFAULT_CLUSTER_THRESHOLD
    db_session.refresh(cluster1)
    assert cluster1.metadata_["document_count"] == 2

    # Document 3: Completely distinct event (earthquake in Japan)
    loc_jp = Entity(
        entity_type="COUNTRY",
        canonical_name="Japan",
        normalized_name="japan",
        country_code="JP",
        metadata_={},
    )
    db_session.add(loc_jp)
    db_session.flush()

    doc3 = Document(
        source_id=sample_source.id,
        title="Major 6.8 Magnitude Earthquake Hits Coastal Japan",
        url="https://example.com/quake/1",
        published_at=now,
        content_hash=compute_content_hash("Quake 1", "url3"),
        processing_status="NORMALIZED",
    )
    db_session.add(doc3)
    db_session.flush()

    ev3 = ExtractedEvent(
        document_id=doc3.id,
        event_type="natural_disaster",
        event_title="Major 6.8 Magnitude Earthquake Strikes Coastal Japan",
        event_time=now,
        location_entity_id=loc_jp.id,
        confidence=0.98,
        importance=0.92,
    )
    db_session.add(ev3)
    db_session.commit()

    # Cluster Event 3 -> Must NOT merge into ECB cluster
    mem3 = cluster_extracted_event(db_session, ev3.id)
    assert mem3.event_cluster_id != cluster1.id
    cluster3 = db_session.get(EventCluster, mem3.event_cluster_id)
    assert cluster3.event_type == "natural_disaster"
    assert cluster3.primary_location_entity_id == loc_jp.id
