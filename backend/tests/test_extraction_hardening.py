"""V0.2.1 Extraction Hardening Regression Test Suite.

Verifies:
1. Negation detection (positive vs negated pairs)
2. Historical and retrospective temporal filtering
3. Prepositional event location disambiguation
4. Contextual entity role extraction
5. Demonym and alias false-positive protection
6. Generic indicator de-aliasing
7. Uncataloged entity recall (Vanuatu, Solomon Islands, Tbilisi)
8. Ambiguous entity disambiguation (Georgia country vs US state)
9. Multi-event invariance
"""

import uuid
from datetime import datetime, timezone
import pytest

from backend.app.extractors.rules import RuleBasedIntelligenceExtractor
from backend.app.extractors.normalizer import (
    EntityNormalizer,
    disambiguate_georgia_context,
)
from backend.app.schemas.extraction import EntityType, EntityRole, EventType


@pytest.fixture
def extractor():
    return RuleBasedIntelligenceExtractor(version="0.2.1")


# ==============================================================================
# 1. NEGATION HANDLING TESTS
# ==============================================================================
def test_negation_rate_decision_pair(extractor):
    # Positive case
    pos_res = extractor.extract(
        document_id=uuid.uuid4(),
        title="Fed raises rates by 25 basis points to combat inflation",
        description="Federal Reserve officials announced the interest rate decision today.",
        published_at=datetime.now(timezone.utc),
    )
    assert any(e.event_type == EventType.CENTRAL_BANK_DECISION.value for e in pos_res.events)

    # Negated case: "will not raise rates"
    neg_res = extractor.extract(
        document_id=uuid.uuid4(),
        title="Federal Reserve Chairman Confirms Central Bank Will Not Raise Rates",
        description="Jerome Powell denied that a rate hike was under consideration, ruling out any benchmark rate increase.",
        content="The Federal Reserve made clear it decided not to raise interest rates despite rising inflation concerns.",
        published_at=datetime.now(timezone.utc),
    )
    assert not any(e.event_type == EventType.CENTRAL_BANK_DECISION.value for e in neg_res.events)


def test_negation_sanctions_pair(extractor):
    # Positive case
    pos_res = extractor.extract(
        document_id=uuid.uuid4(),
        title="Government approved sanctions against foreign shipping fleet",
        published_at=datetime.now(timezone.utc),
    )
    assert any(e.event_type == EventType.SANCTION.value for e in pos_res.events)

    # Negated case: "denied plans to approve sanctions"
    neg_res = extractor.extract(
        document_id=uuid.uuid4(),
        title="Government denied plans to approve sanctions against foreign shipping fleet",
        published_at=datetime.now(timezone.utc),
    )
    assert not any(e.event_type == EventType.SANCTION.value for e in neg_res.events)


def test_negation_acquisition_pair(extractor):
    # Positive case
    pos_res = extractor.extract(
        document_id=uuid.uuid4(),
        title="NVIDIA Enters Agreement to Acquire Software Platform Provider",
        published_at=datetime.now(timezone.utc),
    )
    assert any(e.event_type == EventType.CORPORATE_ACTION.value for e in pos_res.events)

    # Negated case: "ruled out an acquisition"
    neg_res = extractor.extract(
        document_id=uuid.uuid4(),
        title="NVIDIA ruled out an acquisition of European software provider",
        published_at=datetime.now(timezone.utc),
    )
    assert not any(e.event_type == EventType.CORPORATE_ACTION.value for e in neg_res.events)


# ==============================================================================
# 2. TEMPORAL / HISTORICAL RETROSPECTIVE FILTERING TESTS
# ==============================================================================
def test_historical_retrospective_suppression(extractor):
    # Retrospective analysis: 1990 Gulf War
    res = extractor.extract(
        document_id=uuid.uuid4(),
        title="Reflections on the 1990 Gulf War Missile Attack and Its Impact on Oil Markets",
        description="Historical retrospective examining the military invasion thirty-six years ago.",
        content="Historians review how the 1990 missile attack and military invasion reshaped crude oil pricing across decades.",
        published_at=datetime.now(timezone.utc),
    )
    # Must NOT emit active conflict event
    assert not any(e.event_type == EventType.CONFLICT.value for e in res.events)


def test_historical_financial_crisis_suppression(extractor):
    res = extractor.extract(
        document_id=uuid.uuid4(),
        title="Analysis of the 2008 financial crisis and liquidity facility interventions",
        content="Economists revisit lessons from the 2008 financial crisis twenty years later.",
        published_at=datetime.now(timezone.utc),
    )
    assert not any(e.event_type == EventType.CENTRAL_BANK_DECISION.value for e in res.events)


def test_current_event_with_future_or_current_year_preserved(extractor):
    # Valid breaking news with forward reference year 2026
    res = extractor.extract(
        document_id=uuid.uuid4(),
        title="Federal Reserve raises rates in 2026 after inflation prints surge",
        description="Policymakers in Washington announced the benchmark rate decision this morning.",
        published_at=datetime.now(timezone.utc),
    )
    assert any(e.event_type == EventType.CENTRAL_BANK_DECISION.value for e in res.events)


# ==============================================================================
# 3. EVENT LOCATION DISAMBIGUATION TESTS
# ==============================================================================
def test_location_disambiguation_actor_before_location(extractor):
    # Actors (US, UK) appear before event location (Ukraine)
    res = extractor.extract(
        document_id=uuid.uuid4(),
        title="United States and United Kingdom Issue Joint Condemnation of Drone Strike in Ukraine",
        description="Washington and London released statements condemning a missile attack on electrical substations in Kyiv.",
        content="Officials in the United States and Britain reaffirmed support as air defense units in Ukraine intercepted projectiles.",
        published_at=datetime.now(timezone.utc),
    )
    conflict_events = [e for e in res.events if e.event_type == EventType.CONFLICT.value]
    assert len(conflict_events) == 1
    # Event location must be Ukraine, NOT United States
    assert conflict_events[0].location_entity_name == "Ukraine"


def test_location_disambiguation_location_before_actor(extractor):
    res = extractor.extract(
        document_id=uuid.uuid4(),
        title="In Tokyo, Ministers from Germany and France Sign Trilateral Energy Accord",
        published_at=datetime.now(timezone.utc),
    )
    agreements = [e for e in res.events if e.event_type == EventType.INTERNATIONAL_AGREEMENT.value]
    assert len(agreements) == 1
    assert agreements[0].location_entity_name == "Tokyo"


def test_location_disambiguation_irrelevant_headquarters_context(extractor):
    res = extractor.extract(
        document_id=uuid.uuid4(),
        title="Officials in London Discuss Air Defense Interception Over the Red Sea",
        description="Defense ministry confirmed missile attack intercepted outside shipping corridors in the Red Sea.",
        published_at=datetime.now(timezone.utc),
    )
    conflict_events = [e for e in res.events if e.event_type in (EventType.CONFLICT.value, EventType.MILITARY_ACTION.value)]
    assert len(conflict_events) >= 1
    # Event location should be Red Sea, not London
    assert conflict_events[0].location_entity_name == "Red Sea"


# ==============================================================================
# 4. CONTEXTUAL ENTITY ROLE TESTS
# ==============================================================================
def test_contextual_roles_actors_vs_locations(extractor):
    res = extractor.extract(
        document_id=uuid.uuid4(),
        title="Germany, France, and Italy Sign Trilateral Industrial Energy Protocol",
        description="Ministers met in Berlin to formalize the gas pipeline agreement.",
        published_at=datetime.now(timezone.utc),
    )
    ent_map = {e.canonical_name: e.role for e in res.entities}
    # Germany, France, Italy are sovereign signatories -> actor
    assert ent_map.get("Germany") == EntityRole.ACTOR.value
    assert ent_map.get("France") == EntityRole.ACTOR.value
    assert ent_map.get("Italy") == EntityRole.ACTOR.value
    # Berlin follows 'in Berlin' -> location
    assert ent_map.get("Berlin") == EntityRole.LOCATION.value


def test_contextual_roles_biographical_background(extractor):
    res = extractor.extract(
        document_id=uuid.uuid4(),
        title="Retired Diplomat Born in Canada and Educated in Japan Reflects on Memoirs from Alpine Cottage in Switzerland",
        description="Personal autobiographical feature covering childhood travels in Canada, visiting relatives in Japan, and hiking in Switzerland.",
        published_at=datetime.now(timezone.utc),
    )
    ent_map = {e.canonical_name: e.role for e in res.entities}
    # Passive background mentions must be 'other', NOT 'actor' or state 'location'
    assert ent_map.get("Canada") == EntityRole.OTHER.value
    assert ent_map.get("Japan") == EntityRole.OTHER.value
    assert ent_map.get("Switzerland") == EntityRole.OTHER.value


def test_company_role_actor_vs_audience(extractor):
    # Corporate actor
    res_actor = extractor.extract(
        document_id=uuid.uuid4(),
        title="NVIDIA Enters Agreement to Acquire Software Platform Provider",
        published_at=datetime.now(timezone.utc),
    )
    ent_map_actor = {e.canonical_name: e.role for e in res_actor.entities}
    assert ent_map_actor.get("NVIDIA") == EntityRole.ACTOR.value

    # Passive audience attendee
    res_audience = extractor.extract(
        document_id=uuid.uuid4(),
        title="Tech Forum in London Discusses European Art Heritage with Microsoft Representative in Audience",
        description="Cultural symposium attended by Microsoft delegate who listened to historical presentations.",
        published_at=datetime.now(timezone.utc),
    )
    ent_map_aud = {e.canonical_name: e.role for e in res_audience.entities}
    assert ent_map_aud.get("Microsoft") == EntityRole.OTHER.value


# ==============================================================================
# 5. DEMONYM AND ALIAS FALSE-POSITIVE TESTS
# ==============================================================================
def test_demonym_does_not_trigger_european_union_or_euro(extractor):
    res = extractor.extract(
        document_id=uuid.uuid4(),
        title="The Evolution of Coffee Culture and Urban Social Gatherings in Eighteenth Century Europe",
        description="Historians examine European art and culinary architecture across European nations.",
        published_at=datetime.now(timezone.utc),
    )
    extracted_canonical = [e.canonical_name for e in res.entities]
    assert "European Union" not in extracted_canonical
    assert "Euro" not in extracted_canonical
    assert len(res.events) == 0


def test_explicit_european_union_and_euro_resolve_correctly(extractor):
    res = extractor.extract(
        document_id=uuid.uuid4(),
        title="European Union Approves Billion Euro Trade Package in Brussels",
        published_at=datetime.now(timezone.utc),
    )
    extracted_canonical = [e.canonical_name for e in res.entities]
    assert "European Union" in extracted_canonical
    assert "Euro" in extracted_canonical


# ==============================================================================
# 6. UNCATALOGED ENTITY RECALL & DISAMBIGUATION TESTS
# ==============================================================================
def test_vanuatu_and_solomon_islands_extracted(extractor):
    res = extractor.extract(
        document_id=uuid.uuid4(),
        title="Republic of Vanuatu Signs Maritime Fishing Accord with Solomon Islands",
        description="Officials from Vanuatu and Solomon Islands met in Honiara.",
        published_at=datetime.now(timezone.utc),
    )
    ent_map = {e.canonical_name: e.entity_type for e in res.entities}
    assert "Vanuatu" in ent_map
    assert ent_map["Vanuatu"] == EntityType.COUNTRY.value
    assert "Solomon Islands" in ent_map
    assert ent_map["Solomon Islands"] == EntityType.COUNTRY.value
    assert "Honiara" in ent_map
    assert ent_map["Honiara"] == EntityType.CITY.value


def test_georgia_country_disambiguation(extractor):
    # Georgia the sovereign nation in Caucasus
    res_country = extractor.extract(
        document_id=uuid.uuid4(),
        title="Parliamentary Election Results Spark Demonstrations in Tbilisi",
        description="Citizens across Georgia voted in the general election as opposition coalitions challenged results.",
        published_at=datetime.now(timezone.utc),
    )
    georgia_ent = next((e for e in res_country.entities if e.canonical_name == "Georgia"), None)
    assert georgia_ent is not None
    assert georgia_ent.entity_type == EntityType.COUNTRY.value
    assert georgia_ent.country_code == "GE"


def test_georgia_us_state_disambiguation(extractor):
    # Georgia the US state
    res_state = extractor.extract(
        document_id=uuid.uuid4(),
        title="Governor Addresses Georgia State Legislature in Atlanta",
        description="Debate in the Georgia state senate regarding county tax allocations.",
        published_at=datetime.now(timezone.utc),
    )
    georgia_ent = next((e for e in res_state.entities if e.canonical_name == "Georgia"), None)
    assert georgia_ent is not None
    assert georgia_ent.country_code == "US"


# ==============================================================================
# 7. MULTI-EVENT INVARIANCE TESTS
# ==============================================================================
def test_multi_event_extraction_remains_intact(extractor):
    res = extractor.extract(
        document_id=uuid.uuid4(),
        title="Central Bank Hikes Rates as Rocket Attack Erupts Along Northern Frontier",
        description="Israel central bank raised its benchmark rate while military air defense intercepted missile strike barrage.",
        published_at=datetime.now(timezone.utc),
    )
    event_types = [e.event_type for e in res.events]
    assert EventType.CENTRAL_BANK_DECISION.value in event_types
    assert EventType.CONFLICT.value in event_types
    # Both events extracted distinctly without duplicates
    assert len(event_types) == len(set(event_types))
