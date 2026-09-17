import pytest
import uuid
from backend.app.extractors.relationship import DeterministicRelationshipExtractor
from backend.app.schemas.relationship import RelationshipType


def test_relationship_extraction_with_aliases():
    extractor = DeterministicRelationshipExtractor()

    entities = [
        {"id": uuid.uuid4(), "canonical_name": "United States", "entity_type": "COUNTRY"},
        {"id": uuid.uuid4(), "canonical_name": "Russian Federation", "entity_type": "COUNTRY"},
    ]

    sentence = "The US imposed sanctions on Russia following recent developments."
    doc_id = uuid.uuid4()

    rels = extractor.extract_relationships_from_sentence(
        sentence=sentence,
        entities=entities,
        document_id=doc_id,
    )

    assert len(rels) >= 1
    sanction_rel = rels[0]
    assert sanction_rel.relationship_type == RelationshipType.SANCTIONS
    assert sanction_rel.source_entity_id == entities[0]["id"]
    assert sanction_rel.target_entity_id == entities[1]["id"]
    assert sanction_rel.confidence >= 0.80
    assert len(sanction_rel.evidence) >= 20
    assert sanction_rel.source_document_id == doc_id


def test_relationship_signed_agreement_with():
    extractor = DeterministicRelationshipExtractor()

    entities = [
        {"id": uuid.uuid4(), "canonical_name": "United Kingdom", "entity_type": "COUNTRY"},
        {"id": uuid.uuid4(), "canonical_name": "Japan", "entity_type": "COUNTRY"},
    ]

    sentence = "The UK signed an agreement with Japan to deepen security and trade cooperation."
    doc_id = uuid.uuid4()

    rels = extractor.extract_relationships_from_sentence(
        sentence=sentence,
        entities=entities,
        document_id=doc_id,
    )

    assert len(rels) >= 1
    rel = next((r for r in rels if r.relationship_type == RelationshipType.SIGNED_AGREEMENT_WITH), None)
    assert rel is not None
    assert rel.confidence >= 0.80


def test_relationship_negation_suppressed():
    extractor = DeterministicRelationshipExtractor()

    entities = [
        {"id": uuid.uuid4(), "canonical_name": "United States", "entity_type": "COUNTRY"},
        {"id": uuid.uuid4(), "canonical_name": "Russian Federation", "entity_type": "COUNTRY"},
    ]

    sentence = "Washington denied that the US imposed sanctions on Russia yesterday."
    rels = extractor.extract_relationships_from_sentence(
        sentence=sentence,
        entities=entities,
    )

    assert len(rels) == 0
