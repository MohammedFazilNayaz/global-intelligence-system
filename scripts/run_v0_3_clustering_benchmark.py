"""V0.3 Clustering Benchmark Runner.

Executes a comprehensive, deterministic 17-scenario benchmark (A through Q)
evaluating event deduplication, candidate blocking, and clustering accuracy against ground truth.
Calculates:
- Cluster Pair Precision, Recall, F1
- False Merge Rate, Missed Merge Rate
- Ambiguous Match Rate, Duplicate Membership Rate
"""
import os
import sys
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Set, Tuple, Any
from collections import defaultdict

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import sessionmaker, joinedload

from backend.app.db.base import Base
from backend.app.db.session import engine, SessionLocal
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.services.extraction_service import extract_from_document
from backend.app.services.clustering_service import cluster_document_events, get_cluster_for_event
from backend.app.processors.hasher import compute_content_hash


def init_benchmark_db():
    Base.metadata.create_all(bind=engine)
    return engine, SessionLocal


def build_corpus_documents() -> List[Dict[str, Any]]:
    """Define the 17 deterministic evaluation documents and their expected real-world cluster keys."""
    t0 = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)

    return [
        # --- Scenario A: Same event, different wording (ECB rate hike) ---
        {
            "id": "A1",
            "title": "European Central Bank Raises Benchmark Interest Rates by 25 Basis Points",
            "desc": "The European Central Bank raised interest rates in Frankfurt as inflation moderates.",
            "content": "European Central Bank policymakers voted to raise benchmark interest rates by 25 basis points.",
            "published_at": t0 + timedelta(hours=2),
            "source": "Reuters",
            "expected_cluster": "CLUSTER_A_ECB_HIKE",
        },
        {
            "id": "A2",
            "title": "ECB Increases Key Benchmark Rate by Quarter Percentage Point",
            "desc": "Central bank officials at the European Central Bank lifted policy rates.",
            "content": "The ECB increases key benchmark rate by a quarter point to restrain inflation pressures.",
            "published_at": t0 + timedelta(hours=2, minutes=15),
            "source": "Bloomberg",
            "expected_cluster": "CLUSTER_A_ECB_HIKE",
        },

        # --- Scenario B: Same event, different source ---
        {
            "id": "B1",
            "title": "Germany, France, and Italy Sign Trilateral Industrial Energy Protocol",
            "desc": "Representatives met in Berlin to ratify natural gas accord.",
            "content": "Germany, France, and Italy sign trilateral industrial energy protocol in Berlin.",
            "published_at": t0 - timedelta(hours=2),
            "source": "Reuters",
            "expected_cluster": "CLUSTER_B_ENERGY_ACCORD",
        },
        {
            "id": "B2",
            "title": "Berlin Summit: France, Germany, and Italy Ratify Energy Security Pact",
            "desc": "Ministers in Berlin finalized European industrial protocol.",
            "content": "Delegations from France, Germany, and Italy ratify trilateral energy security pact in Berlin.",
            "published_at": t0 - timedelta(hours=1, minutes=35),
            "source": "Associated Press",
            "expected_cluster": "CLUSTER_B_ENERGY_ACCORD",
        },

        # --- Scenario C: Same event, different sentence structure (passive vs active) ---
        {
            "id": "C1",
            "title": "OPEC Extends Crude Oil Production Cut Quotas Through Next Quarter",
            "desc": "Delegates in Saudi Arabia approved extension of crude oil quotas.",
            "content": "OPEC extends crude oil production cut quotas through next quarter following Vienna ministerial review.",
            "published_at": t0 + timedelta(hours=3),
            "source": "Platts",
            "expected_cluster": "CLUSTER_C_OPEC_QUOTA",
        },
        {
            "id": "C2",
            "title": "Crude Oil Production Quota Reductions Were Extended Through Next Quarter by OPEC",
            "desc": "Supply reductions continued as ministers confirmed agreement in Saudi Arabia.",
            "content": "Crude oil production quota reductions were extended through next quarter by OPEC delegates.",
            "published_at": t0 + timedelta(hours=3, minutes=30),
            "source": "Argus",
            "expected_cluster": "CLUSTER_C_OPEC_QUOTA",
        },

        # --- Scenario D: Same event with different actor ordering ---
        {
            "id": "D1",
            "title": "United States and United Kingdom Finalize Maritime Security Accord in London",
            "desc": "US and UK officials met in London.",
            "content": "United States and United Kingdom finalize maritime security accord in London.",
            "published_at": t0 - timedelta(hours=1),
            "source": "BBC",
            "expected_cluster": "CLUSTER_D_MARITIME_ACCORD",
        },
        {
            "id": "D2",
            "title": "United Kingdom and United States Seal Strategic Maritime Security Accord in London",
            "desc": "British and American diplomats signed agreement in London.",
            "content": "United Kingdom and United States seal strategic maritime security accord in London.",
            "published_at": t0 - timedelta(minutes=40),
            "source": "Sky News",
            "expected_cluster": "CLUSTER_D_MARITIME_ACCORD",
        },

        # --- Scenario E: Same event with city/country references ---
        {
            "id": "E1",
            "title": "Air Defense Intercepts Drone Strike Barrage in Kyiv",
            "desc": "Air defense units engaged aerial targets over the Ukrainian capital.",
            "content": "Air defense intercepts drone strike barrage in Kyiv following dawn missile alarm.",
            "published_at": t0 - timedelta(hours=6),
            "source": "Kyiv Post",
            "expected_cluster": "CLUSTER_E_DRONE_STRIKE",
        },
        {
            "id": "E2",
            "title": "Military Forces Repel Major Drone Attack in Ukraine Overnight",
            "desc": "Defenses engaged hostile unmanned aircraft in Kyiv.",
            "content": "Armed forces repel major drone attack in Ukraine overnight, shooting down multiple drones.",
            "published_at": t0 - timedelta(hours=5, minutes=15),
            "source": "Reuters",
            "expected_cluster": "CLUSTER_E_DRONE_STRIKE",
        },

        # --- Scenario F: Same event with missing location ---
        {
            "id": "F1",
            "title": "Consumer Price Index Rose 0.4 Percent in August as Headline Inflation Hits Multi-Month High",
            "desc": "Government statistics office reported consumer price index acceleration.",
            "content": "Consumer Price Index rose 0.4 percent in August as headline inflation accelerated.",
            "published_at": t0 + timedelta(minutes=30),
            "source": "Dow Jones",
            "expected_cluster": "CLUSTER_F_CPI_RELEASE",
        },
        {
            "id": "F2",
            "title": "August Consumer Price Index Climbs 0.4 Percent Ahead of Central Bank Policy Meeting",
            "desc": "Consumer Price Index rose 0.4 percent.",
            "content": "August Consumer Price Index climbs 0.4 percent with broad increases across shelter and energy.",
            "published_at": t0 + timedelta(minutes=45),
            "source": "Financial Times",
            "expected_cluster": "CLUSTER_F_CPI_RELEASE",
        },

        # --- Scenario G: Same event with missing event time (fallback to pub date) ---
        {
            "id": "G1",
            "title": "Republic of Vanuatu Signs Maritime Fishing Accord with Solomon Islands in Honiara",
            "desc": "Pacific island representatives concluded negotiations.",
            "content": "Republic of Vanuatu signs maritime fishing accord with Solomon Islands in Honiara.",
            "published_at": t0 - timedelta(hours=4),
            "source": "Radio NZ",
            "expected_cluster": "CLUSTER_G_VANUATU_SOLOMON",
        },
        {
            "id": "G2",
            "title": "Solomon Islands and Vanuatu Ratify Historic Bilateral Maritime Fishing Accord",
            "desc": "Leaders in Honiara affirmed regional treaty.",
            "content": "Solomon Islands and Vanuatu ratify historic bilateral maritime fishing accord in Honiara.",
            "published_at": t0 - timedelta(hours=3, minutes=30),
            "source": "Pacific News",
            "expected_cluster": "CLUSTER_G_VANUATU_SOLOMON",
        },

        # --- Scenario H: Different events, same actors (US actions) ---
        {
            "id": "H1",
            "title": "United States Imposes New Economic Sanctions on Foreign Drone Manufacturers",
            "desc": "Washington announced asset freeze sanctions on foreign entities.",
            "content": "United States imposes new economic sanctions on foreign drone manufacturers.",
            "published_at": t0 + timedelta(hours=1),
            "source": "Washington Post",
            "expected_cluster": "CLUSTER_H1_US_SANCTIONS",
        },
        {
            "id": "H2",
            "title": "United States Announces Comprehensive Bilateral Tech Trade Pact with Japan",
            "desc": "Trade representatives announced semiconductor accord.",
            "content": "United States announces comprehensive bilateral tech trade pact with Japan.",
            "published_at": t0 + timedelta(hours=1, minutes=10),
            "source": "Nikkei",
            "expected_cluster": "CLUSTER_H2_US_JAPAN_TRADE",
        },

        # --- Scenario I: Different events, same location (Tokyo) ---
        {
            "id": "I1",
            "title": "Severe 6.5 Magnitude Earthquake Strikes Off the Coast of Tokyo",
            "desc": "Tremors felt across coastal Japan.",
            "content": "Severe 6.5 magnitude earthquake strikes off the coast of Tokyo.",
            "published_at": t0 - timedelta(hours=3),
            "source": "NHK",
            "expected_cluster": "CLUSTER_I1_TOKYO_QUAKE",
        },
        {
            "id": "I2",
            "title": "Tokyo Hosts Trilateral Asian Diplomatic Conference on Pacific Trade",
            "desc": "Delegates gathered in Tokyo.",
            "content": "Tokyo hosts trilateral Asian diplomatic conference on Pacific trade agreements.",
            "published_at": t0 - timedelta(hours=2, minutes=30),
            "source": "Japan Times",
            "expected_cluster": "CLUSTER_I2_TOKYO_CONFERENCE",
        },

        # --- Scenario J: Different events, same event type, different sovereign countries ---
        {
            "id": "J1",
            "title": "Catastrophic 7.2 Magnitude Earthquake Strikes Southern Coastal Provinces in Japan",
            "desc": "Emergency rescue operations underway in Japan.",
            "content": "Catastrophic 7.2 magnitude earthquake strikes southern coastal provinces in Japan.",
            "published_at": t0 - timedelta(hours=8),
            "source": "Asahi",
            "expected_cluster": "CLUSTER_J1_JAPAN_QUAKE",
        },
        {
            "id": "J2",
            "title": "Magnitude 7.4 Earthquake Devastates Coastal Communities in Chile",
            "desc": "Tsunami alerts issued across Pacific coast.",
            "content": "Magnitude 7.4 earthquake devastates coastal communities in Chile.",
            "published_at": t0 - timedelta(hours=7, minutes=30),
            "source": "El Mercurio",
            "expected_cluster": "CLUSTER_J2_CHILE_QUAKE",
        },

        # --- Scenario K: Same company, separate corporate actions ---
        {
            "id": "K1",
            "title": "NVIDIA Enters Agreement to Acquire Software Platform Provider for Five Billion Dollars",
            "desc": "NVIDIA announced major acquisition.",
            "content": "NVIDIA enters agreement to acquire software platform provider for five billion dollars.",
            "published_at": t0 + timedelta(hours=4),
            "source": "CNBC",
            "expected_cluster": "CLUSTER_K1_NVIDIA_ACQUISITION",
        },
        {
            "id": "K2",
            "title": "NVIDIA Authorizes Twenty Billion Dollar Share Repurchase Program",
            "desc": "Board approved capital return plan.",
            "content": "NVIDIA authorizes twenty billion dollar share repurchase program for institutional investors.",
            "published_at": t0 + timedelta(hours=4, minutes=15),
            "source": "MarketWatch",
            "expected_cluster": "CLUSTER_K2_NVIDIA_BUYBACK",
        },

        # --- Scenario L: Same central bank, separate decisions separated by months ---
        {
            "id": "L1",
            "title": "Federal Reserve Raises Benchmark Interest Rates by 25 Basis Points in June Meeting",
            "desc": "Federal Reserve policy decision in June.",
            "content": "Federal Reserve raises benchmark interest rates by 25 basis points in June meeting.",
            "published_at": t0 - timedelta(days=80),
            "source": "Bloomberg",
            "expected_cluster": "CLUSTER_L1_FED_JUNE",
        },
        {
            "id": "L2",
            "title": "Federal Reserve Raises Benchmark Interest Rates by 25 Basis Points in September Meeting",
            "desc": "Federal Reserve policy decision in September.",
            "content": "Federal Reserve raises benchmark interest rates by 25 basis points in September meeting.",
            "published_at": t0,
            "source": "WSJ",
            "expected_cluster": "CLUSTER_L2_FED_SEPTEMBER",
        },

        # --- Scenario M: Historical reference vs current event ---
        {
            "id": "M1",
            "title": "Reflections on the 1990 Gulf War Missile Attack and Its Impact on Oil Markets",
            "desc": "Historical retrospective analysis.",
            "content": "Reflections on the 1990 Gulf War missile attack and its lasting impact on crude oil markets.",
            "published_at": t0,
            "source": "History Review",
            "expected_cluster": "CLUSTER_M1_HISTORICAL",  # Suppressed by V0.2.1 extractor
        },
        {
            "id": "M2",
            "title": "Naval Forces Intercept Cruise Missile Strike in the Red Sea",
            "desc": "Active military engagement in the Red Sea.",
            "content": "Naval forces intercept cruise missile strike in the Red Sea following maritime escalation.",
            "published_at": t0 + timedelta(hours=5),
            "source": "USNI News",
            "expected_cluster": "CLUSTER_M2_CURRENT_MISSILE",
        },

        # --- Scenario N: Events separated by meaningful time (>48h) ---
        {
            "id": "N1",
            "title": "Air Defense Intercepts Drone Strike Barrage Near Port City Infrastructure",
            "desc": "Port city air defenses intercepted hostile drone.",
            "content": "Air defense intercepts drone strike barrage near port city infrastructure.",
            "published_at": t0 - timedelta(days=7),
            "source": "Maritime Bulletin",
            "expected_cluster": "CLUSTER_N1_OLD_STRIKE",
        },
        {
            "id": "N2",
            "title": "Air Defense Intercepts Drone Strike Barrage Near Port City Infrastructure",
            "desc": "New attack on port infrastructure one week later.",
            "content": "Air defense intercepts drone strike barrage near port city infrastructure.",
            "published_at": t0,
            "source": "Maritime Bulletin",
            "expected_cluster": "CLUSTER_N2_NEW_STRIKE",
        },

        # --- Scenario O: Exact duplicate documents ---
        {
            "id": "O1",
            "title": "Prime Minister Resigns Following No-Confidence Vote in Paris",
            "desc": "French political crisis deepened.",
            "content": "Prime Minister resigns following no-confidence vote in Paris parliament.",
            "published_at": t0 + timedelta(hours=6),
            "source": "Le Figaro",
            "expected_cluster": "CLUSTER_O_PM_RESIGN",
        },
        {
            "id": "O2",
            "title": "Prime Minister Resigns Following No-Confidence Vote in Paris",
            "desc": "French political crisis deepened.",
            "content": "Prime Minister resigns following no-confidence vote in Paris parliament.",
            "published_at": t0 + timedelta(hours=6, minutes=5),
            "source": "France24",
            "expected_cluster": "CLUSTER_O_PM_RESIGN",
        },

        # --- Scenario P: Near duplicate documents ---
        {
            "id": "P1",
            "title": "Parliamentary Election Results Spark Demonstrations in Tbilisi",
            "desc": "Georgia election dispute.",
            "content": "Parliamentary election results spark demonstrations in Tbilisi as opposition disputes vote tally.",
            "published_at": t0 + timedelta(hours=7),
            "source": "Civil Georgia",
            "expected_cluster": "CLUSTER_P_TBILISI_ELECTION",
        },
        {
            "id": "P2",
            "title": "Thousands Protest Across Tbilisi Following Disputed Parliamentary Election Results",
            "desc": "Crowds in Georgia capital.",
            "content": "Thousands protest across Tbilisi following disputed parliamentary election results.",
            "published_at": t0 + timedelta(hours=7, minutes=20),
            "source": "Euronews",
            "expected_cluster": "CLUSTER_P_TBILISI_ELECTION",
        },

        # --- Scenario Q: Multi-event document ---
        {
            "id": "Q1",
            "title": "Central Bank Hikes Rates as Rocket Attack Erupts Along Northern Frontier",
            "desc": "Dual crisis unfolds in Israel.",
            "content": "Central bank hikes rates as rocket attack erupts along northern frontier in Israel.",
            "published_at": t0 + timedelta(hours=8),
            "source": "Haaretz",
            "expected_cluster": "MULTI_EVENT_Q",  # Generates 2 events
        },
        {
            "id": "Q2",
            "title": "Central Bank Raises Benchmark Rates by Fifty Basis Points to Curb Price Rises",
            "desc": "Monetary policy decision in Israel.",
            "content": "Central bank raises benchmark rates by fifty basis points to curb price rises in Israel.",
            "published_at": t0 + timedelta(hours=8, minutes=15),
            "source": "Globes",
            "expected_cluster": "CLUSTER_Q_RATES",
        },
        {
            "id": "Q3",
            "title": "Rocket Attack Erupts Along Northern Frontier Following Cross-Border Escalation",
            "desc": "Border artillery and rocket barrages.",
            "content": "Rocket attack erupts along northern frontier in Israel damaging border infrastructure.",
            "published_at": t0 + timedelta(hours=8, minutes=20),
            "source": "Jerusalem Post",
            "expected_cluster": "CLUSTER_Q_CONFLICT",
        },
    ]


def run_benchmark():
    print("=" * 90)
    print("GLOBAL INTELLIGENCE PLATFORM — V0.3 CLUSTERING QUALITY BENCHMARK")
    print("=" * 90)

    engine, Session = init_benchmark_db()
    engine.echo = False
    session = Session()

    # Clean previous benchmark test data
    session.execute(delete(EventClusterMember))
    session.execute(delete(EventCluster))
    session.execute(delete(ExtractedEvent))
    session.execute(delete(DocumentEntity))
    session.execute(delete(Document))
    session.execute(delete(Source))
    session.commit()

    # Create sources
    sources_by_name: Dict[str, Source] = {}
    corpus = build_corpus_documents()
    source_names = {doc["source"] for doc in corpus}
    for s_name in sorted(source_names):
        src = Source(
            name=s_name,
            source_type="rss",
            base_url="https://example.com",
            feed_url=f"https://example.com/rss/{s_name.lower().replace(' ', '_')}",
            active=True,
        )
        session.add(src)
        session.flush()
        sources_by_name[s_name] = src
    session.commit()

    # Ingest and extract all documents
    print("\n>>> Ingesting and Extracting Benchmark Documents...")
    extracted_events_info: List[Dict[str, Any]] = []
    doc_id_to_expected_cluster: Dict[uuid.UUID, str] = {}

    for item in corpus:
        doc = Document(
            source_id=sources_by_name[item["source"]].id,
            title=item["title"],
            description=item["desc"],
            content=item["content"],
            url=f"https://example.com/doc/{item['id'].lower()}",
            published_at=item["published_at"],
            content_hash=compute_content_hash(item["title"], item["id"]),
            processing_status="NORMALIZED",
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)

        # Run V0.2.1 intelligence extraction (with auto_cluster=True)
        res = extract_from_document(session, doc.id, auto_cluster=True)
        doc_events = list(
            session.scalars(
                select(ExtractedEvent).where(ExtractedEvent.document_id == doc.id)
            ).all()
        )

        for ev in doc_events:
            # Map expected cluster
            if item["id"] == "Q1":
                if ev.event_type == "central_bank_decision":
                    exp_clust = "CLUSTER_Q_RATES"
                else:
                    exp_clust = "CLUSTER_Q_CONFLICT"
            else:
                exp_clust = item["expected_cluster"]

            extracted_events_info.append({
                "doc_id": doc.id,
                "doc_key": item["id"],
                "event_id": ev.id,
                "event_type": ev.event_type,
                "title": ev.event_title,
                "expected_cluster": exp_clust,
            })

    print(f"  Total Extracted Events Available for Clustering: {len(extracted_events_info)}")

    # Retrieve all cluster assignments
    print("\n>>> Evaluating Deterministic Cluster Assignments...")
    event_to_predicted_cluster: Dict[uuid.UUID, uuid.UUID] = {}
    event_to_score: Dict[uuid.UUID, float] = {}
    duplicate_memberships = 0

    for ev_info in extracted_events_info:
        ev_id = ev_info["event_id"]
        memberships = list(
            session.scalars(
                select(EventClusterMember).where(EventClusterMember.extracted_event_id == ev_id)
            ).all()
        )
        if len(memberships) > 1:
            duplicate_memberships += 1
        if memberships:
            event_to_predicted_cluster[ev_id] = memberships[0].event_cluster_id
            event_to_score[ev_id] = memberships[0].membership_score

    # Calculate Pairwise Clustering Metrics
    N = len(extracted_events_info)
    total_pairs = N * (N - 1) // 2

    tp = 0  # Same in ground truth, same in predicted
    fp = 0  # Different in ground truth, same in predicted (False Merge)
    fn = 0  # Same in ground truth, different in predicted (Missed Merge)
    tn = 0  # Different in ground truth, different in predicted

    false_merges_list: List[Tuple[str, str, str]] = []
    missed_merges_list: List[Tuple[str, str, str]] = []

    for i in range(N):
        for j in range(i + 1, N):
            e1 = extracted_events_info[i]
            e2 = extracted_events_info[j]

            gt_same = (e1["expected_cluster"] == e2["expected_cluster"])
            pred_same = (
                event_to_predicted_cluster.get(e1["event_id"]) is not None
                and event_to_predicted_cluster.get(e1["event_id"])
                == event_to_predicted_cluster.get(e2["event_id"])
            )

            if gt_same and pred_same:
                tp += 1
            elif not gt_same and pred_same:
                fp += 1
                false_merges_list.append((e1["title"][:40], e2["title"][:40], f"{e1['expected_cluster']} != {e2['expected_cluster']}"))
            elif gt_same and not pred_same:
                fn += 1
                missed_merges_list.append((e1["title"][:40], e2["title"][:40], e1["expected_cluster"]))
            else:
                tn += 1

    precision = (tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 100.0
    recall = (tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 100.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    total_gt_negative = fp + tn
    total_gt_positive = tp + fn
    false_merge_rate = (fp / total_gt_negative) * 100.0 if total_gt_negative > 0 else 0.0
    missed_merge_rate = (fn / total_gt_positive) * 100.0 if total_gt_positive > 0 else 0.0

    # Distinct clusters formed
    unique_clusters = list(session.scalars(select(EventCluster).where(EventCluster.status == "ACTIVE")).all())

    print("\n" + "=" * 90)
    print("V0.3 CLUSTERING BENCHMARK RESULTS")
    print("=" * 90)
    print(f"Total Extracted Events Evaluated: {N}")
    print(f"Total Evaluated Event Pairs     : {total_pairs}")
    print(f"Active EventClusters Formed     : {len(unique_clusters)}")
    print("-" * 90)
    print(f"True Positives (Correct Merges) : {tp}")
    print(f"True Negatives (Correct Splits) : {tn}")
    print(f"False Positives (False Merges)  : {fp}")
    print(f"False Negatives (Missed Merges) : {fn}")
    print("-" * 90)
    print(f"CLUSTER PAIR PRECISION          : {precision:.1f}%  (Target: >= 95.0%)")
    print(f"CLUSTER PAIR RECALL             : {recall:.1f}%  (Target: >= 90.0%)")
    print(f"CLUSTER PAIR F1                 : {f1:.1f}%  (Target: >= 92.0%)")
    print(f"FALSE MERGE RATE                : {false_merge_rate:.2f}%  (Target: <= 5.0%)")
    print(f"MISSED MERGE RATE               : {missed_merge_rate:.2f}%")
    print(f"DUPLICATE MEMBERSHIP COUNT      : {duplicate_memberships}  (Target: 0)")
    print("=" * 90)

    if false_merges_list:
        print("\n[DETECTED FALSE MERGES]:")
        for m in false_merges_list:
            print(f"  - '{m[0]}' MERGED WITH '{m[1]}' ({m[2]})")

    if missed_merges_list:
        print("\n[DETECTED MISSED MERGES]:")
        for m in missed_merges_list:
            print(f"  - '{m[0]}' AND '{m[1]}' DID NOT MERGE (Expected: {m[2]})")

    # Verify gates
    gates_passed = (
        precision >= 95.0
        and recall >= 90.0
        and f1 >= 92.0
        and false_merge_rate <= 5.0
        and duplicate_memberships == 0
    )

    if gates_passed:
        print("\n>>> ALL V0.3 QUANTITATIVE ENGINEERING GATES SATISFIED DECISIVELY!")
    else:
        print("\n>>> ONE OR MORE V0.3 GATES FAILED!")

    return gates_passed


if __name__ == "__main__":
    success = run_benchmark()
    sys.exit(0 if success else 1)
