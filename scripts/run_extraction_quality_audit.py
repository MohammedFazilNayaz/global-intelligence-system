"""Strict V0.2 Extraction Quality Audit Runner.

Evaluates the current V0.2 RuleBasedIntelligenceExtractor and EntityNormalizer
against a deterministic benchmark corpus of 20 difficult test documents.
Measures Entity & Event Precision, Recall, F1, Role Accuracy, Negation handling,
Historical reference filtering, Location disambiguation, and Reprocessing.
"""

import os
import sys
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Set, Tuple
from dataclasses import dataclass, field
from pydantic import BaseModel

# Quiet verbose SQL engine logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.extractors.rules import RuleBasedIntelligenceExtractor
from backend.app.extractors.normalizer import EntityNormalizer, normalize_text_key
from backend.app.schemas.extraction import ExtractionResult, EntityType, EventType
from backend.app.db.session import SessionLocal, engine
engine.echo = False
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.event import ExtractedEvent
from backend.app.services.extraction_service import extract_from_document
from backend.app.services.source_service import create_source
from backend.app.schemas.source import SourceCreate
from backend.app.processors.hasher import compute_content_hash
from sqlalchemy import select, func


@dataclass
class ExpectedEntity:
    canonical_name: str
    entity_type: str
    role: str
    aliases: List[str] = field(default_factory=list)


@dataclass
class ExpectedEvent:
    event_type: str
    is_real_event: bool = True  # False for negations or historical retrospectives
    location_canonical: str = ""
    min_importance: float = 0.5


@dataclass
class AuditDocument:
    id: int
    category: str
    title: str
    description: str
    content: str
    expected_entities: List[ExpectedEntity]
    expected_events: List[ExpectedEvent]


# ==============================================================================
# DETERMINISTIC TEST CORPUS: 20 DIFFICULT CASES
# ==============================================================================
BENCHMARK_CORPUS: List[AuditDocument] = [
    # 1. Straightforward single-event article
    AuditDocument(
        id=1,
        category="1. Straightforward Single-Event",
        title="European Central Bank Raises Benchmark Interest Rates by 25 Basis Points",
        description="Policymakers in Frankfurt announced the monetary policy decision to contain inflation pressures.",
        content="President Christine Lagarde noted that benchmark interest rate hikes remain the primary tool.",
        expected_entities=[
            ExpectedEntity("European Central Bank", "CENTRAL_BANK", "actor", ["ECB"]),
            ExpectedEntity("Interest Rates", "ECONOMIC_INDICATOR", "indicator"),
            ExpectedEntity("Consumer Price Index", "ECONOMIC_INDICATOR", "indicator"),
        ],
        expected_events=[
            ExpectedEvent(event_type="central_bank_decision", is_real_event=True, location_canonical="", min_importance=0.8),
        ],
    ),

    # 2. Multiple entities of the same type (Countries)
    AuditDocument(
        id=2,
        category="2. Multiple Entities Same Type",
        title="Germany, France, and Italy Sign Trilateral Industrial Energy Protocol",
        description="The three European nations coordinated cross-border gas and power grid resilience.",
        content="Ministers met in Berlin to formalize the gas pipeline and natural gas storage framework.",
        expected_entities=[
            ExpectedEntity("Germany", "COUNTRY", "actor"),
            ExpectedEntity("France", "COUNTRY", "actor"),
            ExpectedEntity("Italy", "COUNTRY", "actor"),
            ExpectedEntity("Berlin", "CITY", "location"),
            ExpectedEntity("Natural Gas", "COMMODITY", "commodity"),
        ],
        expected_events=[
            ExpectedEvent(event_type="international_agreement", is_real_event=True, location_canonical="Berlin", min_importance=0.8),
        ],
    ),

    # 3. Multiple different event types in one document
    AuditDocument(
        id=3,
        category="3. Multiple Different Event Types",
        title="Central Bank Hikes Rates as Rocket Attack Erupts Along Northern Frontier",
        description="Israel central bank raised its benchmark rate while military air defense intercepted missile strike barrage.",
        content="Clashes erupted across the border as financial authorities held an emergency monetary policy session.",
        expected_entities=[
            ExpectedEntity("Israel", "COUNTRY", "location"),
            ExpectedEntity("Interest Rates", "ECONOMIC_INDICATOR", "indicator"),
        ],
        expected_events=[
            ExpectedEvent(event_type="central_bank_decision", is_real_event=True, min_importance=0.8),
            ExpectedEvent(event_type="conflict", is_real_event=True, min_importance=0.9),
        ],
    ),

    # 4. Multiple events in one document (Trade + Natural Disaster)
    AuditDocument(
        id=4,
        category="4. Multiple Distinct Events",
        title="Tokyo Ratifies Trade Agreement Hours Before Severe Magnitude Earthquake Strikes Offshore",
        description="Japan approved the bilateral trade deal before a magnitude earthquake triggered coastal warnings.",
        content="Officials in Tokyo confirmed customs duties relief while disaster relief teams mobilized.",
        expected_entities=[
            ExpectedEntity("Japan", "COUNTRY", "actor"),
            ExpectedEntity("Tokyo", "CITY", "location"),
        ],
        expected_events=[
            ExpectedEvent(event_type="trade_action", is_real_event=True, min_importance=0.7),
            ExpectedEvent(event_type="natural_disaster", is_real_event=True, min_importance=0.8),
        ],
    ),

    # 5. Negated statement (Central bank did NOT raise rates)
    AuditDocument(
        id=5,
        category="5. Negated Statement",
        title="Federal Reserve Chairman Confirms Central Bank Will Not Raise Rates",
        description="Jerome Powell denied that a rate hike was under consideration, ruling out any benchmark rate increase.",
        content="The Federal Reserve made clear it decided not to raise interest rates despite rising inflation concerns.",
        expected_entities=[
            ExpectedEntity("Federal Reserve", "CENTRAL_BANK", "actor"),
            ExpectedEntity("Interest Rates", "ECONOMIC_INDICATOR", "indicator"),
        ],
        expected_events=[
            # Crucial test: A rate hike did NOT occur!
            # If the extractor extracts a "central_bank_decision" rate hike simply because "raise rates" / "rate hike" appears, this is an extraction flaw.
            ExpectedEvent(event_type="central_bank_decision", is_real_event=False),
        ],
    ),

    # 6. Historical reference that is NOT a current event
    AuditDocument(
        id=6,
        category="6. Historical Reference",
        title="Reflections on the 1990 Gulf War Missile Attack and Its Impact on Oil Markets",
        description="Historical retrospective examining the military invasion thirty-six years ago.",
        content="Historians review how the 1990 missile attack and military invasion reshaped crude oil pricing across decades.",
        expected_entities=[
            ExpectedEntity("Crude Oil", "COMMODITY", "commodity"),
        ],
        expected_events=[
            # Crucial test: No current conflict or military invasion occurred today!
            ExpectedEvent(event_type="conflict", is_real_event=False),
        ],
    ),

    # 7. Entity mentioned but NOT the actor/subject of the event
    AuditDocument(
        id=7,
        category="7. Entity Mentioned But Not Actor",
        title="Tech Forum in London Discusses European Art Heritage with Microsoft Representative in Audience",
        description="A cultural symposium in London featured lectures on medieval architecture attended by a Microsoft product specialist.",
        content="The Microsoft delegate listened to historical presentations regarding British museum archives.",
        expected_entities=[
            ExpectedEntity("London", "CITY", "location"),
            ExpectedEntity("Microsoft", "COMPANY", "other"),
        ],
        expected_events=[],  # No geopolitical or corporate action event
    ),

    # 8. Multiple countries where only one is the actual event location
    AuditDocument(
        id=8,
        category="8. Multiple Countries with One Event Location",
        title="United States and United Kingdom Issue Joint Condemnation of Drone Strike in Ukraine",
        description="Washington and London released statements condemning a missile attack on electrical substations in Kyiv.",
        content="Officials in the United States and Britain reaffirmed support as air defense units in Ukraine intercepted projectiles.",
        expected_entities=[
            ExpectedEntity("United States", "COUNTRY", "actor"),
            ExpectedEntity("United Kingdom", "COUNTRY", "actor"),
            ExpectedEntity("Ukraine", "COUNTRY", "location"),
            ExpectedEntity("Kyiv", "CITY", "location"),
            ExpectedEntity("Washington, D.C.", "CITY", "actor"),
            ExpectedEntity("London", "CITY", "actor"),
        ],
        expected_events=[
            # The event location is Ukraine/Kyiv, NOT the United States or London
            ExpectedEvent(event_type="conflict", is_real_event=True, location_canonical="Ukraine"),
        ],
    ),

    # 9. Common abbreviations and aliases
    AuditDocument(
        id=9,
        category="9. Common Abbreviations and Aliases",
        title="US and UAE Finalize LNG Supply Agreement in NYC Denominated in USD",
        description="Trade delegations from UAE and US signed accord for liquefied natural gas deliveries.",
        content="The contract relies on Natural Gas infrastructure with clearance through US Dollar settlement accounts.",
        expected_entities=[
            ExpectedEntity("United States", "COUNTRY", "actor", ["US"]),
            ExpectedEntity("United Arab Emirates", "COUNTRY", "actor", ["UAE"]),
            ExpectedEntity("New York City", "CITY", "location", ["NYC"]),
            ExpectedEntity("Natural Gas", "COMMODITY", "commodity", ["LNG"]),
            ExpectedEntity("US Dollar", "CURRENCY", "currency", ["USD"]),
        ],
        expected_events=[
            ExpectedEvent(event_type="international_agreement", is_real_event=True),
        ],
    ),

    # 10. Unknown / unseen entities not in curated knowledge base
    AuditDocument(
        id=10,
        category="10. Unknown Unseen Entities",
        title="Republic of Vanuatu Signs Maritime Fishing Accord with Solomon Islands",
        description="Pacific island governments agreed to bilateral boundary protections in Honiara.",
        content="Officials from Vanuatu and Solomon Islands announced mutual fishing quota limits.",
        expected_entities=[
            ExpectedEntity("Vanuatu", "COUNTRY", "actor"),
            ExpectedEntity("Solomon Islands", "COUNTRY", "actor"),
        ],
        expected_events=[
            ExpectedEvent(event_type="international_agreement", is_real_event=True),
        ],
    ),

    # 11. Similar or ambiguous entity names (Georgia the country vs Georgia US state)
    AuditDocument(
        id=11,
        category="11. Ambiguous Entity Names",
        title="Parliamentary Election Results Spark Demonstrations in Tbilisi",
        description="Citizens across Georgia voted in the general election as international observers monitored ballot count.",
        content="Opposition coalitions in Georgia challenged election results declared by the national electoral bureau.",
        expected_entities=[
            ExpectedEntity("Georgia", "COUNTRY", "location"),  # Country in Caucasus, not US state
        ],
        expected_events=[
            ExpectedEvent(event_type="election", is_real_event=True, location_canonical="Georgia"),
        ],
    ),

    # 12. Financial terminology without central bank decision
    AuditDocument(
        id=12,
        category="12. Financial Terminology",
        title="Yield Curve Inversion Deepens Across Sovereign Debt Markets",
        description="Benchmark bond yields adjusted downward as institutional managers shifted liquidity reserves.",
        content="Long-duration treasury yields compressed relative to short-term bills amid portfolio hedging.",
        expected_entities=[],
        expected_events=[],  # No central bank rate decision took place
    ),

    # 13. Economic indicators release
    AuditDocument(
        id=13,
        category="13. Economic Indicators",
        title="Consumer Price Index Rose 0.4 Percent in August as Headline Inflation Hits Multi-Month High",
        description="Labor bureau reported CPI rose above analyst forecasts driven by motor fuel and shelter costs.",
        content="The Consumer Price Index increased while core inflation prints remained elevated.",
        expected_entities=[
            ExpectedEntity("Consumer Price Index", "ECONOMIC_INDICATOR", "indicator"),
        ],
        expected_events=[
            ExpectedEvent(event_type="economic_release", is_real_event=True),
        ],
    ),

    # 14. Political developments (Prime minister resignation)
    AuditDocument(
        id=14,
        category="14. Political Developments",
        title="Prime Minister Resigns Following No-Confidence Vote in Paris",
        description="French head of government tendered resignation to the president after legislative defeat.",
        content="The Prime Minister resigned as opposition parties in France united to pass a motion of censure in Paris.",
        expected_entities=[
            ExpectedEntity("France", "COUNTRY", "location"),
            ExpectedEntity("Paris", "CITY", "location"),
        ],
        expected_events=[
            ExpectedEvent(event_type="political_change", is_real_event=True, location_canonical="France"),
        ],
    ),

    # 15. Corporate developments (M&A)
    AuditDocument(
        id=15,
        category="15. Corporate Developments",
        title="NVIDIA Enters Agreement to Acquire Software Platform Provider for Five Billion Dollars",
        description="Semiconductor manufacturer NVIDIA announced merger agreement with infrastructure developer.",
        content="The corporate board approved the transaction to acquire assets subject to antitrust clearance.",
        expected_entities=[
            ExpectedEntity("NVIDIA", "COMPANY", "actor"),
        ],
        expected_events=[
            ExpectedEvent(event_type="corporate_action", is_real_event=True),
        ],
    ),

    # 16. Conflict / military terminology
    AuditDocument(
        id=16,
        category="16. Conflict and Military Terminology",
        title="Air Defense Intercepts Drone Strike Barrage Near Port City Infrastructure",
        description="Military units deployed electronic countermeasures following rocket attack sirens.",
        content="Artillery fire and airstrike detonations were recorded outside suburban residential corridors.",
        expected_entities=[],
        expected_events=[
            ExpectedEvent(event_type="conflict", is_real_event=True, min_importance=0.9),
        ],
    ),

    # 17. Commodity developments (OPEC quota)
    AuditDocument(
        id=17,
        category="17. Commodity Developments",
        title="OPEC Approves Extension of Crude Oil Production Cut Quotas Through Next Quarter",
        description="Energy delegates in Vienna finalized the crude output ceiling to balance global petroleum inventories.",
        content="Saudi Arabia supported maintaining production quota limits on Brent Crude shipments.",
        expected_entities=[
            ExpectedEntity("OPEC", "INTERNATIONAL_ORGANIZATION", "actor"),
            ExpectedEntity("Crude Oil", "COMMODITY", "commodity"),
            ExpectedEntity("Saudi Arabia", "COUNTRY", "actor"),
        ],
        expected_events=[
            ExpectedEvent(event_type="commodity_event", is_real_event=True, min_importance=0.8),
        ],
    ),

    # 18. Article with NO meaningful event (Editorial/Cultural history)
    AuditDocument(
        id=18,
        category="18. No Event (Cultural Essay)",
        title="The Evolution of Coffee Culture and Urban Social Gatherings in Eighteenth Century Europe",
        description="An essay tracing the social influence of public coffee establishments across historical capitals.",
        content="Historians examine the architecture and culinary customs that emerged during the Enlightenment across European centers.",
        expected_entities=[],
        expected_events=[],  # Crucial test: MUST NOT extract any geopolitical or economic event!
    ),

    # 19. Noisy/unrelated entity mentions
    AuditDocument(
        id=19,
        category="19. Noisy Unrelated Entity Mentions",
        title="Retired Diplomat Born in Canada and Educated in Japan Reflects on Memoirs from Alpine Cottage in Switzerland",
        description="Personal autobiographical feature covering childhood travels and landscape photography.",
        content="Author discusses memories of growing up in Canada, visiting relatives in Japan, and hiking in Switzerland.",
        expected_entities=[
            # Entities are present, but NOT actors or locations of state events
            ExpectedEntity("Canada", "COUNTRY", "other"),
            ExpectedEntity("Japan", "COUNTRY", "other"),
            ExpectedEntity("Switzerland", "COUNTRY", "other"),
        ],
        expected_events=[],  # No geopolitical or economic event!
    ),

    # 20. Distinct events with different confidence/importance levels
    AuditDocument(
        id=20,
        category="20. Multi-Event Disparate Severity",
        title="Catastrophic 7.8 Magnitude Earthquake Devastates Southern Provinces as Municipal Board Approves Sanitation Ordinance",
        description="Thousands injured in disaster zone while regional committee voted on town sanitation regulations.",
        content="Tsunami warnings and flash flooding followed the magnitude earthquake while local officials enacted sanitation decrees.",
        expected_entities=[],
        expected_events=[
            ExpectedEvent(event_type="natural_disaster", is_real_event=True, min_importance=0.85),
            ExpectedEvent(event_type="government_decision", is_real_event=True, min_importance=0.50),
        ],
    ),
]


def run_extraction_quality_audit():
    print("=" * 90)
    print("STRICT V0.2 EXTRACTION QUALITY AUDIT — BENCHMARK EVALUATION")
    print("=" * 90)

    extractor = RuleBasedIntelligenceExtractor()

    # Metrics collectors
    entity_tp = 0
    entity_fp = 0
    entity_fn = 0
    entity_type_correct = 0
    entity_norm_correct = 0
    entity_role_correct = 0

    event_tp = 0
    event_fp = 0
    event_fn = 0
    event_type_correct = 0
    event_location_correct = 0
    event_location_evaluated = 0

    negation_failures = 0
    historical_failures = 0
    false_positive_events = 0
    duplicate_events_count = 0

    audit_failures: List[Dict[str, Any]] = []

    for doc in BENCHMARK_CORPUS:
        print(f"\n--- [Doc #{doc.id:02d}] {doc.category} ---")
        print(f"Title: {doc.title}")

        # Run extraction
        result: ExtractionResult = extractor.extract(
            document_id=uuid.uuid4(),
            title=doc.title,
            description=doc.description,
            content=doc.content,
            published_at=datetime.now(timezone.utc),
        )

        extracted_entities = result.entities
        extracted_events = result.events

        # -------------------------------------------------------------
        # ENTITY EVALUATION
        # -------------------------------------------------------------
        matched_expected_entities = set()
        matched_extracted_entities = set()

        for exp_idx, exp_ent in enumerate(doc.expected_entities):
            # Check if any extracted entity matches this expected entity
            found_match = False
            for ext_idx, ext_ent in enumerate(extracted_entities):
                if ext_idx in matched_extracted_entities:
                    continue
                # Match canonical or alias
                if (
                    normalize_text_key(ext_ent.canonical_name) == normalize_text_key(exp_ent.canonical_name)
                    or any(normalize_text_key(a) == normalize_text_key(ext_ent.canonical_name) for a in exp_ent.aliases)
                    or normalize_text_key(ext_ent.mention_text) == normalize_text_key(exp_ent.canonical_name)
                ):
                    found_match = True
                    matched_expected_entities.add(exp_idx)
                    matched_extracted_entities.add(ext_idx)
                    entity_tp += 1

                    # Type accuracy
                    if ext_ent.entity_type.upper() == exp_ent.entity_type.upper():
                        entity_type_correct += 1
                    else:
                        audit_failures.append({
                            "doc_id": doc.id,
                            "category": "Entity Type Mismatch",
                            "input_text": doc.title,
                            "expected": f"{exp_ent.canonical_name} as {exp_ent.entity_type}",
                            "actual": f"{ext_ent.canonical_name} as {ext_ent.entity_type}",
                            "cause": "Taxonomy classification heuristic mismatch",
                        })

                    # Normalization accuracy
                    if normalize_text_key(ext_ent.canonical_name) == normalize_text_key(exp_ent.canonical_name):
                        entity_norm_correct += 1

                    # Role accuracy
                    if ext_ent.role.lower() == exp_ent.role.lower():
                        entity_role_correct += 1
                    else:
                        audit_failures.append({
                            "doc_id": doc.id,
                            "category": "Entity Role Mismatch",
                            "input_text": doc.title,
                            "expected": f"Role '{exp_ent.role}' for {exp_ent.canonical_name}",
                            "actual": f"Role '{ext_ent.role}'",
                            "cause": "Static rule assigns role purely based on type or title presence",
                        })
                    break

            if not found_match:
                entity_fn += 1
                audit_failures.append({
                    "doc_id": doc.id,
                    "category": "Entity False Negative (Missed Mention)",
                    "input_text": doc.title,
                    "expected": f"Mention of {exp_ent.canonical_name} ({exp_ent.entity_type})",
                    "actual": "Not extracted",
                    "cause": "Entity not present in curated knowledge base or pattern regex boundary",
                })

        # False positive entities
        for ext_idx, ext_ent in enumerate(extracted_entities):
            if ext_idx not in matched_extracted_entities:
                entity_fp += 1
                audit_failures.append({
                    "doc_id": doc.id,
                    "category": "Entity False Positive",
                    "input_text": doc.title,
                    "expected": "No extraction for this entity",
                    "actual": f"Extracted '{ext_ent.canonical_name}' ({ext_ent.entity_type})",
                    "cause": "Keyword matched common noun or peripheral mention",
                })

        # -------------------------------------------------------------
        # EVENT EVALUATION
        # -------------------------------------------------------------
        # Check duplicate events of the same type
        event_types_extracted = [ev.event_type for ev in extracted_events]
        if len(event_types_extracted) != len(set(event_types_extracted)):
            duplicate_events_count += (len(event_types_extracted) - len(set(event_types_extracted)))

        # Expected real events
        real_expected_events = [ev for ev in doc.expected_events if ev.is_real_event]
        negated_or_historical_events = [ev for ev in doc.expected_events if not ev.is_real_event]

        # Check negation / historical false positives
        for non_ev in negated_or_historical_events:
            for ext_ev in extracted_events:
                if ext_ev.event_type == non_ev.event_type:
                    event_fp += 1
                    false_positive_events += 1
                    if "Negated" in doc.category:
                        negation_failures += 1
                        audit_failures.append({
                            "doc_id": doc.id,
                            "category": "Negation Failure (False Event)",
                            "input_text": doc.title,
                            "expected": f"No event of type '{non_ev.event_type}' (explicitly negated)",
                            "actual": f"Extracted event '{ext_ev.title}' ({ext_ev.event_type}) with conf={ext_ev.confidence}",
                            "cause": "Extractor checks keyword substring presence with zero negation parsing",
                        })
                    elif "Historical" in doc.category:
                        historical_failures += 1
                        audit_failures.append({
                            "doc_id": doc.id,
                            "category": "Historical Reference Failure (False Event)",
                            "input_text": doc.title,
                            "expected": f"No current event of type '{non_ev.event_type}' (retrospective analysis)",
                            "actual": f"Extracted event '{ext_ev.title}' ({ext_ev.event_type})",
                            "cause": "Extractor does not differentiate past historical context from breaking news",
                        })

        # If document had no events expected at all (doc 18, 19, etc.)
        if not real_expected_events and not negated_or_historical_events:
            for ext_ev in extracted_events:
                event_fp += 1
                false_positive_events += 1
                audit_failures.append({
                    "doc_id": doc.id,
                    "category": "No-Event False Positive",
                    "input_text": doc.title,
                    "expected": "0 extracted events (editorial/essay/noise)",
                    "actual": f"Extracted event '{ext_ev.title}' ({ext_ev.event_type})",
                    "cause": "Keyword triggered on generic word in non-event text",
                })

        # Match real expected events
        matched_expected_events = set()
        matched_extracted_events = set()

        for exp_idx, exp_ev in enumerate(real_expected_events):
            found_ev = False
            for ext_idx, ext_ev in enumerate(extracted_events):
                if ext_idx in matched_extracted_events:
                    continue
                if ext_ev.event_type == exp_ev.event_type:
                    found_ev = True
                    matched_expected_events.add(exp_idx)
                    matched_extracted_events.add(ext_idx)
                    event_tp += 1
                    event_type_correct += 1

                    # Location evaluation if specified
                    if exp_ev.location_canonical:
                        event_location_evaluated += 1
                        if ext_ev.location_entity_name and normalize_text_key(ext_ev.location_entity_name) == normalize_text_key(exp_ev.location_canonical):
                            event_location_correct += 1
                        else:
                            audit_failures.append({
                                "doc_id": doc.id,
                                "category": "Event Location Disambiguation Failure",
                                "input_text": doc.title,
                                "expected": f"Event location '{exp_ev.location_canonical}'",
                                "actual": f"Assigned location '{ext_ev.location_entity_name}'",
                                "cause": "Location heuristic blindly takes first location candidate in document",
                            })
                    break

            if not found_ev:
                event_fn += 1
                audit_failures.append({
                    "doc_id": doc.id,
                    "category": "Event False Negative (Missed Event)",
                    "input_text": doc.title,
                    "expected": f"Event of type '{exp_ev.event_type}'",
                    "actual": "No event extracted of this type",
                    "cause": "Trigger vocabulary gap or pattern mismatch",
                })

        for ext_idx, ext_ev in enumerate(extracted_events):
            if ext_idx not in matched_extracted_events:
                # Check if it was already counted under negation/historical/no-event FP
                if not any(ext_ev.event_type == non_ev.event_type for non_ev in negated_or_historical_events) and real_expected_events:
                    event_fp += 1
                    false_positive_events += 1
                    audit_failures.append({
                        "doc_id": doc.id,
                        "category": "Spurious Event False Positive",
                        "input_text": doc.title,
                        "expected": "No secondary event of this type",
                        "actual": f"Extracted '{ext_ev.event_type}' (trigger: '{ext_ev.metadata.get('trigger_word')}')",
                        "cause": "Overly broad keyword trigger matched incidental text",
                    })

        # Print per-document summary
        print(f"  Extracted Entities: {[e.canonical_name for e in extracted_entities]}")
        print(f"  Extracted Events: {[(ev.event_type, ev.confidence, ev.importance, ev.location_entity_name) for ev in extracted_events]}")

    # -----------------------------------------------------------------
    # COMPUTE QUANTITATIVE METRICS
    # -----------------------------------------------------------------
    entity_precision = (entity_tp / (entity_tp + entity_fp)) if (entity_tp + entity_fp) > 0 else 0.0
    entity_recall = (entity_tp / (entity_tp + entity_fn)) if (entity_tp + entity_fn) > 0 else 0.0
    entity_f1 = (2 * entity_precision * entity_recall / (entity_precision + entity_recall)) if (entity_precision + entity_recall) > 0 else 0.0

    entity_type_acc = (entity_type_correct / entity_tp) if entity_tp > 0 else 0.0
    entity_norm_acc = (entity_norm_correct / entity_tp) if entity_tp > 0 else 0.0
    entity_role_acc = (entity_role_correct / entity_tp) if entity_tp > 0 else 0.0

    event_precision = (event_tp / (event_tp + event_fp)) if (event_tp + event_fp) > 0 else 0.0
    event_recall = (event_tp / (event_tp + event_fn)) if (event_tp + event_fn) > 0 else 0.0
    event_f1 = (2 * event_precision * event_recall / (event_precision + event_recall)) if (event_precision + event_recall) > 0 else 0.0

    event_loc_acc = (event_location_correct / event_location_evaluated) if event_location_evaluated > 0 else 0.0

    print("\n" + "=" * 90)
    print("AUDIT METRICS SUMMARY")
    print("=" * 90)
    print(f"Entity TP: {entity_tp} | FP: {entity_fp} | FN: {entity_fn}")
    print(f"ENTITY PRECISION : {entity_precision:.1%}")
    print(f"ENTITY RECALL    : {entity_recall:.1%}")
    print(f"ENTITY F1        : {entity_f1:.1%}")
    print(f"  - Type Accuracy         : {entity_type_acc:.1%}")
    print(f"  - Normalization Accuracy: {entity_norm_acc:.1%}")
    print(f"  - Role Accuracy         : {entity_role_acc:.1%}")

    print("-" * 90)
    print(f"Event TP: {event_tp} | FP: {event_fp} | FN: {event_fn}")
    print(f"EVENT PRECISION  : {event_precision:.1%}")
    print(f"EVENT RECALL     : {event_recall:.1%}")
    print(f"EVENT F1         : {event_f1:.1%}")
    print(f"  - Event Location Accuracy: {event_loc_acc:.1%}")
    print(f"  - Negation Failures      : {negation_failures}")
    print(f"  - Historical Failures    : {historical_failures}")
    print(f"  - False Positive Events  : {false_positive_events}")
    print(f"  - Duplicate Event Rate   : {duplicate_events_count} duplicates")

    print("\n" + "=" * 90)
    print(f"TOTAL AUDIT FAILURES DETECTED: {len(audit_failures)}")
    print("=" * 90)
    for i, fail in enumerate(audit_failures, 1):
        print(f"\n[Failure #{i:02d}] Doc #{fail['doc_id']} | Category: {fail['category']}")
        print(f"  Input Title: {fail['input_text'][:70]}...")
        print(f"  Expected   : {fail['expected']}")
        print(f"  Actual     : {fail['actual']}")
        print(f"  Root Cause : {fail['cause']}")

    # -----------------------------------------------------------------
    # REPROCESSING VERIFICATION ON LIVE POSTGRESQL 16
    # -----------------------------------------------------------------
    print("\n" + "=" * 90)
    print("REPROCESSING VERIFICATION ON LIVE POSTGRESQL 16")
    print("=" * 90)

    db = SessionLocal()
    try:
        source_in = SourceCreate(
            name=f"Audit Reprocess Source {uuid.uuid4().hex[:6]}",
            source_type="rss",
            base_url="https://audit.example.com",
            feed_url="https://audit.example.com/rss",
        )
        source = create_source(db, source_in)

        doc = Document(
            source_id=source.id,
            title="Federal Reserve Holds Benchmark Rates Steady Amid Inflation Moderation",
            description="Policymakers in Washington maintained target range citing US Dollar stability.",
            url=f"https://audit.example.com/doc/{uuid.uuid4()}",
            published_at=datetime.now(timezone.utc),
            content_hash=compute_content_hash("Audit Doc", f"https://audit.example.com/{uuid.uuid4()}"),
            processing_status="NORMALIZED",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # Run 1: First extraction
        print("Executing Extraction Run 1...")
        resp1 = extract_from_document(db, doc.id)
        db.refresh(doc)
        assert resp1.processing_status == "EXTRACTED"
        run1_entity_count = db.scalar(select(func.count(DocumentEntity.id)).where(DocumentEntity.document_id == doc.id))
        run1_event_count = db.scalar(select(func.count(ExtractedEvent.id)).where(ExtractedEvent.document_id == doc.id))
        print(f"  Run 1 Output: {run1_entity_count} entities, {run1_event_count} events stored.")

        # Run 2: Reprocess extraction
        print("Executing Extraction Run 2 (reprocess=True)...")
        resp2 = extract_from_document(db, doc.id, reprocess=True)
        db.refresh(doc)
        run2_entity_count = db.scalar(select(func.count(DocumentEntity.id)).where(DocumentEntity.document_id == doc.id))
        run2_event_count = db.scalar(select(func.count(ExtractedEvent.id)).where(ExtractedEvent.document_id == doc.id))
        print(f"  Run 2 Output: {run2_entity_count} entities, {run2_event_count} events stored.")

        # Invariant verifications
        assert run2_entity_count == run1_entity_count, "DocumentEntity count changed on duplicate reprocess!"
        assert run2_event_count == run1_event_count, "ExtractedEvent count duplicated on reprocess!"
        assert "extraction_history" in doc.raw_metadata, "extraction_history missing from document raw_metadata!"
        assert len(doc.raw_metadata["extraction_history"]) == 1, "Expected exactly 1 archived run in extraction_history!"
        print("  VERIFIED: Canonical entities reused, document-entity links not duplicated, old output replaced cleanly, extraction history archived.")
    finally:
        db.close()


if __name__ == "__main__":
    run_extraction_quality_audit()
