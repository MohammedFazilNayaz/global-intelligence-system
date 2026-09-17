import uuid
import pytest
from datetime import datetime, timezone
from backend.app.schemas.relationship import RelationshipType, EntityRelationshipCreate
from backend.app.extractors.relationship import DeterministicRelationshipExtractor
from backend.app.extractors.factory import get_extractor
from backend.app.services.event_service import list_events
from backend.app.services.graph_service import (
    create_relationship,
    get_entity_subgraph,
    get_event_relationships,
    get_event_impact_assessment,
    search_graph,
)
from backend.app.models.entity import Entity
from backend.app.models.event import ExtractedEvent
from backend.app.models.document import Document
from backend.app.models.source import Source
from backend.app.processors.hasher import compute_content_hash


def test_extractor_factory():
    ext1 = get_extractor()
    assert ext1 is not None
    ext2 = get_extractor("rule_based")
    assert ext2 is not None
    ext3 = get_extractor("RuleBasedIntelligenceExtractor")
    assert ext3 is not None
    ext4 = get_extractor("non_existent_extractor")
    assert ext4 is not None


def test_relationship_extractor_ontology_and_patterns():
    extractor = DeterministicRelationshipExtractor()

    # 1. Test ontology compatibility
    person = {"id": uuid.uuid4(), "canonical_name": "Satya Nadella", "entity_type": "PERSON"}
    company = {"id": uuid.uuid4(), "canonical_name": "Microsoft", "entity_type": "COMPANY"}
    country1 = {"id": uuid.uuid4(), "canonical_name": "Germany", "entity_type": "COUNTRY"}
    country2 = {"id": uuid.uuid4(), "canonical_name": "France", "entity_type": "COUNTRY"}
    bank = {"id": uuid.uuid4(), "canonical_name": "European Central Bank", "entity_type": "CENTRAL_BANK"}
    currency = {"id": uuid.uuid4(), "canonical_name": "Euro", "entity_type": "CURRENCY"}
    commodity = {"id": uuid.uuid4(), "canonical_name": "Crude Oil", "entity_type": "COMMODITY"}
    sub_co = {"id": uuid.uuid4(), "canonical_name": "GitHub", "entity_type": "COMPANY"}

    assert extractor._is_compatible(person, company, RelationshipType.LEADS) is True
    assert extractor._is_compatible(company, person, RelationshipType.LEADS) is False
    assert extractor._is_compatible(country1, country2, RelationshipType.ALLIED_WITH) is True
    assert extractor._is_compatible(person, country2, RelationshipType.ALLIED_WITH) is False
    assert extractor._is_compatible(bank, currency, RelationshipType.GOVERNS) is True
    assert extractor._is_compatible(company, commodity, RelationshipType.PRODUCES) is True
    assert extractor._is_compatible(country1, commodity, RelationshipType.EXPORTS) is True
    assert extractor._is_compatible(company, sub_co, RelationshipType.OWNS) is True
    assert extractor._is_compatible(company, country1, RelationshipType.OPERATES_IN) is True
    assert extractor._is_compatible(company, country1, RelationshipType.HEADQUARTERED_IN) is True

    # 2. Extract OWNS
    text_owns = "Microsoft owns GitHub and acquired it previously."
    res_owns = extractor.extract_relationships_from_sentence(text_owns, [company, sub_co])
    assert any(r.relationship_type == RelationshipType.OWNS for r in res_owns)

    # 3. Extract OPERATES_IN
    text_operates = "Microsoft operates in Germany under local regulations."
    res_operates = extractor.extract_relationships_from_sentence(text_operates, [company, country1])
    assert any(r.relationship_type == RelationshipType.OPERATES_IN for r in res_operates)

    # 4. Extract EXPORTS
    text_exports = "Germany exports Crude Oil to European partners."
    res_exports = extractor.extract_relationships_from_sentence(text_exports, [country1, commodity])
    assert any(r.relationship_type == RelationshipType.EXPORTS for r in res_exports)

    # 5. Extract PRODUCES
    text_produces = "Microsoft produces Crude Oil in experimental synthetic labs."
    res_produces = extractor.extract_relationships_from_sentence(text_produces, [company, commodity])
    assert any(r.relationship_type == RelationshipType.PRODUCES for r in res_produces)

    # 6. Extract GOVERNS
    text_governs = "European Central Bank governs Euro monetary policies."
    res_governs = extractor.extract_relationships_from_sentence(text_governs, [bank, currency])
    assert any(r.relationship_type == RelationshipType.GOVERNS for r in res_governs)

    # 7. Extract ALLIED_WITH
    text_allied = "Germany formed an alliance with France."
    res_allied = extractor.extract_relationships_from_sentence(text_allied, [country1, country2])
    assert any(r.relationship_type == RelationshipType.ALLIED_WITH for r in res_allied)

    # 8. Hedged sentence confidence penalty
    text_hedged = "Microsoft allegedly owns GitHub."
    res_hedged = extractor.extract_relationships_from_sentence(text_hedged, [company, sub_co])
    if res_hedged:
        assert res_hedged[0].confidence < 0.85

    # 9. Single entity should return empty list
    assert extractor.extract_relationships_from_sentence("Microsoft announced profits.", [company]) == []

    # 10. Long distance separation (>75 chars)
    long_filler = " x" * 50
    long_sentence = f"Microsoft {long_filler} acquired GitHub."
    assert extractor.extract_relationships_from_sentence(long_sentence, [company, sub_co]) == []

    # 11. Passive patterns
    # Passive OWNS: "GitHub is owned by Microsoft." -> Microsoft OWNS GitHub
    text_passive_owns = "GitHub is owned by Microsoft."
    res_p_owns = extractor.extract_relationships_from_sentence(text_passive_owns, [sub_co, company])
    assert any(r.relationship_type == RelationshipType.OWNS and r.source_entity_id == company["id"] and r.target_entity_id == sub_co["id"] for r in res_p_owns)

    # Passive GOVERNS: "Euro is governed by European Central Bank." -> ECB GOVERNS Euro
    text_p_gov = "Euro is governed by European Central Bank."
    res_p_gov = extractor.extract_relationships_from_sentence(text_p_gov, [currency, bank])
    assert any(r.relationship_type == RelationshipType.GOVERNS and r.source_entity_id == bank["id"] and r.target_entity_id == currency["id"] for r in res_p_gov)

    # Passive Negation: "Euro is not governed by Microsoft."
    text_p_neg = "Euro is not governed by Microsoft."
    res_p_neg = extractor.extract_relationships_from_sentence(text_p_neg, [currency, company])
    assert res_p_neg == []

    # Incompatible types for other branches
    intl_org = {"id": uuid.uuid4(), "canonical_name": "United Nations", "entity_type": "INTERNATIONAL_ORGANIZATION"}
    loc = {"id": uuid.uuid4(), "canonical_name": "Berlin", "entity_type": "LOCATION"}
    assert extractor._is_compatible(company, intl_org, RelationshipType.MEMBER_OF) is True
    assert extractor._is_compatible(person, loc, RelationshipType.HEADQUARTERED_IN) is False
    assert extractor._is_compatible(person, loc, RelationshipType.OPERATES_IN) is False
    assert extractor._is_compatible(person, company, RelationshipType.OWNS) is False
    assert extractor._is_compatible(person, currency, RelationshipType.GOVERNS) is False
    assert extractor._is_compatible(person, commodity, RelationshipType.PRODUCES) is False
    assert extractor._is_compatible(person, country1, RelationshipType.ALLIED_WITH) is False


def test_graph_service_edge_cases(db_session):
    # Test non-existent entity traversal
    random_id = uuid.uuid4()
    subgraph = get_entity_subgraph(db_session, entity_id=random_id, depth=2)
    assert subgraph.nodes == []
    assert subgraph.edges == []

    # Test non-existent event relationships
    ev_rels = get_event_relationships(db_session, event_id=random_id)
    assert ev_rels is None

    # Test search_graph with unmatched query
    search_res = search_graph(db_session, query="xyz_non_existent_symbol_12345")
    assert search_res.nodes == []
    assert search_res.edges == []

    # Test invalid relationship creation (missing provenance - whitespace only)
    rel_in = EntityRelationshipCreate(
        source_entity_id=random_id,
        target_entity_id=uuid.uuid4(),
        relationship_type=RelationshipType.HEADQUARTERED_IN,
        confidence=0.9,
        evidence="   ",  # Whitespace provenance
        extraction_method="rule_based",
        extractor_version="v0.7.0",
    )
    with pytest.raises(ValueError, match="Relationship evidence snippet is required"):
        create_relationship(db_session, rel_in)

    # Test missing extractor version
    rel_in.evidence = "Valid evidence text"
    rel_in.extractor_version = ""
    with pytest.raises(ValueError, match="mandatory provenance fields"):
        create_relationship(db_session, rel_in)

    # Test low confidence rejection (<0.50)
    rel_in.extractor_version = "v0.7.0"
    rel_in.confidence = 0.40
    with pytest.raises(ValueError, match="below minimum relationship threshold"):
        create_relationship(db_session, rel_in)

    # Test orphan entity relationship creation
    rel_in.confidence = 0.85
    with pytest.raises(ValueError, match="does not exist"):
        create_relationship(db_session, rel_in)


def test_list_relationships_and_entity_directions(db_session):
    from backend.app.services.graph_service import list_relationships, get_entity_relationships

    ent1 = Entity(
        id=uuid.uuid4(),
        entity_type="COMPANY",
        canonical_name=f"Paginated Test Corp 1 {uuid.uuid4()}",
        normalized_name=f"paginated test corp 1 {uuid.uuid4()}",
        metadata_={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    ent2 = Entity(
        id=uuid.uuid4(),
        entity_type="LOCATION",
        canonical_name=f"Paginated Test City {uuid.uuid4()}",
        normalized_name=f"paginated test city {uuid.uuid4()}",
        metadata_={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add_all([ent1, ent2])
    db_session.commit()

    # Test depth clamping on real entity
    subgraph_d5 = get_entity_subgraph(db_session, entity_id=ent1.id, depth=5)
    assert subgraph_d5.depth == 3
    subgraph_d0 = get_entity_subgraph(db_session, entity_id=ent1.id, depth=0)
    assert subgraph_d0.depth == 1

    rel = create_relationship(
        db_session,
        EntityRelationshipCreate(
            source_entity_id=ent1.id,
            target_entity_id=ent2.id,
            relationship_type=RelationshipType.HEADQUARTERED_IN,
            confidence=0.92,
            evidence="Paginated Test Corp 1 is headquartered in Paginated Test City.",
            extraction_method="deterministic_rules_v0.7",
            extractor_version="v0.7.0",
        ),
    )

    # Test get_entity_relationships
    outbound, inbound = get_entity_relationships(db_session, entity_id=ent1.id)
    assert any(r.id == rel.id for r in outbound)

    outbound2, inbound2 = get_entity_relationships(db_session, entity_id=ent2.id)
    assert any(r.id == rel.id for r in inbound2)

    # Test list_relationships with source_entity_id filter
    items_src, total_src, _ = list_relationships(db_session, source_entity_id=ent1.id)
    assert total_src >= 1
    assert any(r.id == rel.id for r in items_src)

    # Test list_relationships with target_entity_id filter
    items_tgt, total_tgt, _ = list_relationships(db_session, target_entity_id=ent2.id)
    assert total_tgt >= 1

    # Test list_relationships with relationship_type filter
    items_type, total_type, _ = list_relationships(db_session, relationship_type="headquartered_in")
    assert total_type >= 1


def test_source_service_methods(db_session):
    from backend.app.services.source_service import get_source_by_name, list_sources, update_source
    from backend.app.schemas.source import SourceUpdate

    unique_name = f"Source Coverage Test {uuid.uuid4()}"
    src = Source(
        id=uuid.uuid4(),
        name=unique_name,
        base_url="https://source-test.example",
        feed_url="https://source-test.example/rss",
        source_type="rss",
        reliability_score=0.88,
        active=True,
        config_metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(src)
    db_session.commit()

    # get_source_by_name
    found = get_source_by_name(db_session, unique_name)
    assert found is not None
    assert found.id == src.id

    # list_sources with active_only
    items, total = list_sources(db_session, active_only=True)
    assert total >= 1
    assert any(s.id == src.id for s in items)

    # update_source non-existent
    assert update_source(db_session, uuid.uuid4(), SourceUpdate(name="non_existent")) is None

    # update_source existing
    updated = update_source(db_session, src.id, SourceUpdate(reliability_score=0.97))
    assert updated is not None
    assert updated.reliability_score == 0.97


def test_event_service_ordering_filters(db_session):
    now = datetime.now(timezone.utc)
    src = Source(
        id=uuid.uuid4(),
        name=f"Coverage Test Source {uuid.uuid4()}",
        base_url="https://test.example",
        feed_url="https://test.example/feed",
        source_type="rss",
        reliability_score=0.9,
        config_metadata={},
        created_at=now,
        updated_at=now,
    )
    db_session.add(src)
    db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        source_id=src.id,
        title="Coverage Doc",
        content="Testing event ordering filters.",
        content_format="text/plain",
        url=f"https://test.example/{uuid.uuid4()}",
        published_at=now,
        ingested_at=now,
        content_hash=compute_content_hash("Testing event ordering filters.", f"https://test.example/{uuid.uuid4()}"),
        language="en",
        processing_status="PROCESSED",
        raw_metadata={},
        created_at=now,
        updated_at=now,
    )
    db_session.add(doc)
    db_session.flush()

    ev = ExtractedEvent(
        id=uuid.uuid4(),
        document_id=doc.id,
        event_type="test_event",
        event_title="Coverage Event",
        event_summary="Coverage event summary",
        event_time=now,
        confidence=0.85,
        importance=0.75,
        metadata_={},
        created_at=now,
        updated_at=now,
    )
    db_session.add(ev)
    db_session.commit()

    # Test order_by options
    items_created, total, _ = list_events(db_session, order_by="created_at_desc", document_id=doc.id)
    assert total >= 1
    assert len(items_created) >= 1

    items_conf, _, _ = list_events(db_session, order_by="confidence_desc", document_id=doc.id)
    assert len(items_conf) >= 1

    items_time, _, _ = list_events(db_session, order_by="event_time_desc", document_id=doc.id)
    assert len(items_time) >= 1

    items_default, _, _ = list_events(db_session, order_by="importance_desc", document_id=doc.id)
    assert len(items_default) >= 1

