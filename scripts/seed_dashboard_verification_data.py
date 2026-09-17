"""
Seed realistic intelligence corpus into PostgreSQL for V0.4 Dashboard verification.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uuid
from datetime import datetime, timezone, timedelta
from backend.app.db.session import SessionLocal
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.processors.hasher import compute_content_hash

def seed_data():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # 1. Sources
        sources_data = [
            ("Reuters", "https://reuters.com", "reuters_rss"),
            ("Bloomberg News", "https://bloomberg.com", "bloomberg_rss"),
            ("Financial Times", "https://ft.com", "ft_rss"),
            ("Associated Press", "https://apnews.com", "ap_rss"),
            ("Nikkei Asia", "https://asia.nikkei.com", "nikkei_rss"),
        ]
        sources = {}
        for name, url, code in sources_data:
            s = db.query(Source).filter_by(name=name).first()
            if not s:
                s = Source(
                    name=name,
                    base_url=url,
                    feed_url=f"{url}/rss",
                    source_type="rss",
                    reliability_score=0.9,
                    config_metadata={"code": code},
                )
                db.add(s)
                db.flush()
            sources[name] = s

        # 2. Canonical Entities
        entities_data = [
            ("Federal Reserve", "federal reserve", "central_bank", "US", "Central banking system of the United States"),
            ("Jerome Powell", "jerome powell", "person", "US", "Chair of the Federal Reserve"),
            ("European Central Bank", "european central bank", "central_bank", "EU", "Central bank for the euro area"),
            ("Christine Lagarde", "christine lagarde", "person", "EU", "President of the European Central Bank"),
            ("Bank of Japan", "bank of japan", "central_bank", "JP", "Central bank of Japan"),
            ("Kazuo Ueda", "kazuo ueda", "person", "JP", "Governor of the Bank of Japan"),
            ("Securities and Exchange Commission", "securities and exchange commission", "regulator", "US", "US federal securities markets regulator"),
            ("Department of Defense", "department of defense", "government_agency", "US", "US executive branch department of the military"),
            ("Washington", "washington", "location", "US", "Capital city of the United States"),
            ("Frankfurt", "frankfurt", "location", "DE", "Financial center of Germany and seat of the ECB"),
            ("Tokyo", "tokyo", "location", "JP", "Capital city of Japan"),
        ]
        entities = {}
        for cname, nname, etype, ccode, desc in entities_data:
            e = db.query(Entity).filter_by(canonical_name=cname).first()
            if not e:
                e = Entity(canonical_name=cname, normalized_name=nname, entity_type=etype, country_code=ccode, description=desc)
                db.add(e)
                db.flush()
            entities[cname] = e

        # 3. Create Multi-Report Clusters
        # Cluster 1: Fed Rate Decision (Multi-report from Reuters, Bloomberg, FT)
        c1 = EventCluster(
            canonical_title="Federal Reserve Holds Benchmark Policy Rate Steady at 5.25%-5.50%",
            canonical_summary="The Federal Open Market Committee voted unanimously to maintain the federal funds rate in the current target range.",
            event_type="central_bank_decision",
            event_time_start=now - timedelta(hours=3),
            event_time_end=now - timedelta(hours=2),
            primary_location_entity_id=entities["Washington"].id,
            confidence=0.96,
            status="ACTIVE",
            metadata_={
                "importance": 0.92,
                "entities": ["Federal Reserve", "Jerome Powell"],
            }
        )
        db.add(c1)
        db.flush()

        # Documents & Extracted Events for Cluster 1
        c1_reports = [
            (sources["Reuters"], "Fed Leaves Target Rate Unchanged in Unanimous Decision", 0.96, 0.90, "exact_seed", {}),
            (sources["Bloomberg News"], "Federal Reserve Pauses Rates as Inflation Cools", 0.94, 0.92, "pairwise_match", {
                "scores": {
                    "event_type_score": 1.0,
                    "temporal_score": 0.98,
                    "location_score": 1.0,
                    "actor_overlap_score": 0.90,
                    "entity_overlap_score": 0.95,
                    "lexical_score": 0.78,
                    "final_score": 0.93,
                    "threshold": 0.75,
                    "time_diff_minutes": 15,
                }
            }),
            (sources["Financial Times"], "US Central Bank Holds Policy Stance at FOMC Meeting", 0.92, 0.88, "pairwise_match", {
                "scores": {
                    "event_type_score": 1.0,
                    "temporal_score": 0.95,
                    "location_score": 1.0,
                    "actor_overlap_score": 0.80,
                    "entity_overlap_score": 0.85,
                    "lexical_score": 0.72,
                    "final_score": 0.89,
                    "threshold": 0.75,
                    "time_diff_minutes": 25,
                }
            })
        ]

        for src, title, conf, imp, mmeth, meta in c1_reports:
            raw_c = f"{title} content detailing the rate decision."
            doc_url = f"{src.base_url}/news/{uuid.uuid4()}"
            doc = Document(
                source_id=src.id,
                title=title,
                url=doc_url,
                content=raw_c,
                content_hash=compute_content_hash(raw_c, doc_url),
                published_at=now - timedelta(hours=3),
            )
            db.add(doc)
            db.flush()

            ee = ExtractedEvent(
                document_id=doc.id,
                event_type="central_bank_decision",
                event_title=title,
                event_summary=title,
                event_time=now - timedelta(hours=3),
                location_entity_id=entities["Washington"].id,
                confidence=conf,
                importance=imp,
                metadata_={"extractor_version": "rule_based_v0.2.1", "entities": ["Federal Reserve", "Jerome Powell"]},
            )
            db.add(ee)
            db.flush()

            db.add(DocumentEntity(document_id=doc.id, entity_id=entities["Federal Reserve"].id, mention_text="Federal Reserve", entity_role="actor", confidence=0.98))
            db.add(DocumentEntity(document_id=doc.id, entity_id=entities["Jerome Powell"].id, mention_text="Jerome Powell", entity_role="actor", confidence=0.95))

            mem = EventClusterMember(
                event_cluster_id=c1.id,
                extracted_event_id=ee.id,
                membership_score=conf,
                membership_method=mmeth,
                metadata_=meta,
            )
            db.add(mem)

        # Cluster 2: ECB Inflation Assessment (Multi-report from FT & Bloomberg)
        c2 = EventCluster(
            canonical_title="ECB Signals Eurozone Headline Inflation Nearing 2% Target",
            canonical_summary="Christine Lagarde delivered statement on economic outlook in Frankfurt.",
            event_type="inflation_report",
            event_time_start=now - timedelta(hours=8),
            event_time_end=now - timedelta(hours=7),
            primary_location_entity_id=entities["Frankfurt"].id,
            confidence=0.91,
            status="ACTIVE",
            metadata_={
                "importance": 0.82,
                "entities": ["European Central Bank", "Christine Lagarde"],
            }
        )
        db.add(c2)
        db.flush()

        c2_reports = [
            (sources["Financial Times"], "ECB Sees Euro Area Inflation Approaching Benchmark", 0.92, 0.82, "exact_seed", {}),
            (sources["Bloomberg News"], "Lagarde Emphasizes Disinflation Progress Across Europe", 0.90, 0.80, "pairwise_match", {
                "scores": {
                    "event_type_score": 1.0,
                    "temporal_score": 0.97,
                    "location_score": 1.0,
                    "actor_overlap_score": 0.88,
                    "entity_overlap_score": 0.92,
                    "lexical_score": 0.74,
                    "final_score": 0.91,
                    "threshold": 0.75,
                    "time_diff_minutes": 15,
                }
            }),
        ]
        for src, title, conf, imp, mmeth, meta in c2_reports:
            raw_c = f"{title} content detailing inflation progress."
            doc_url = f"{src.base_url}/news/{uuid.uuid4()}"
            doc = Document(
                source_id=src.id,
                title=title,
                url=doc_url,
                content=raw_c,
                content_hash=compute_content_hash(raw_c, doc_url),
                published_at=now - timedelta(hours=8),
            )
            db.add(doc)
            db.flush()

            ee = ExtractedEvent(
                document_id=doc.id,
                event_type="inflation_report",
                event_title=title,
                event_summary=title,
                event_time=now - timedelta(hours=8),
                location_entity_id=entities["Frankfurt"].id,
                confidence=conf,
                importance=imp,
                metadata_={"extractor_version": "rule_based_v0.2.1", "entities": ["European Central Bank", "Christine Lagarde"]},
            )
            db.add(ee)
            db.flush()

            db.add(DocumentEntity(document_id=doc.id, entity_id=entities["European Central Bank"].id, mention_text="European Central Bank", entity_role="actor", confidence=0.98))
            db.add(DocumentEntity(document_id=doc.id, entity_id=entities["Christine Lagarde"].id, mention_text="Christine Lagarde", entity_role="actor", confidence=0.95))

            mem = EventClusterMember(
                event_cluster_id=c2.id,
                extracted_event_id=ee.id,
                membership_score=conf,
                membership_method=mmeth,
                metadata_=meta,
            )
            db.add(mem)

        # Cluster 3: Bank of Japan Policy Adjustment (Tokyo)
        c3 = EventCluster(
            canonical_title="Bank of Japan Reviews Yield Curve Control Policy in Tokyo",
            canonical_summary="Governor Kazuo Ueda announced minor tweaks to market liquidity operations.",
            event_type="central_bank_decision",
            event_time_start=now - timedelta(days=1),
            primary_location_entity_id=entities["Tokyo"].id,
            confidence=0.88,
            status="ACTIVE",
            metadata_={
                "importance": 0.78,
                "entities": ["Bank of Japan", "Kazuo Ueda"],
            }
        )
        db.add(c3)
        db.flush()

        raw_c3 = "Bank of Japan policy adjustments in Tokyo."
        doc3_url = f"{sources['Nikkei Asia'].base_url}/news/{uuid.uuid4()}"
        doc3 = Document(
            source_id=sources["Nikkei Asia"].id,
            title="BOJ Signals Flexibility on Long-Term Rates",
            url=doc3_url,
            content=raw_c3,
            content_hash=compute_content_hash(raw_c3, doc3_url),
            published_at=now - timedelta(days=1),
        )
        db.add(doc3)
        db.flush()

        ee3 = ExtractedEvent(
            document_id=doc3.id,
            event_type="central_bank_decision",
            event_title="BOJ Rate Adjustment",
            event_summary="BOJ Rate Adjustment",
            event_time=now - timedelta(days=1),
            location_entity_id=entities["Tokyo"].id,
            confidence=0.88,
            importance=0.78,
            metadata_={"extractor_version": "rule_based_v0.2.1", "entities": ["Bank of Japan", "Kazuo Ueda"]},
        )
        db.add(ee3)
        db.flush()

        db.add(DocumentEntity(document_id=doc3.id, entity_id=entities["Bank of Japan"].id, mention_text="Bank of Japan", entity_role="actor", confidence=0.98))
        db.add(DocumentEntity(document_id=doc3.id, entity_id=entities["Kazuo Ueda"].id, mention_text="Kazuo Ueda", entity_role="actor", confidence=0.95))

        db.add(EventClusterMember(
            event_cluster_id=c3.id,
            extracted_event_id=ee3.id,
            membership_score=1.0,
            membership_method="exact_seed",
            metadata_={},
        ))

        # Cluster 4: SEC Regulatory Enforcement (Washington)
        c4 = EventCluster(
            canonical_title="SEC Imposes Penalties on Investment Fund Over Disclosure Violations",
            canonical_summary="Regulatory action announced regarding non-compliant representations.",
            event_type="regulatory_enforcement",
            event_time_start=now - timedelta(days=2),
            primary_location_entity_id=entities["Washington"].id,
            confidence=0.94,
            status="ACTIVE",
            metadata_={
                "importance": 0.62,
                "entities": ["Securities and Exchange Commission"],
            }
        )
        db.add(c4)
        db.flush()

        raw_c4 = "SEC imposes civil penalty on asset management advisory firm."
        doc4_url = f"{sources['Associated Press'].base_url}/news/{uuid.uuid4()}"
        doc4 = Document(
            source_id=sources["Associated Press"].id,
            title="SEC Charges Asset Manager with False Climate Disclosures",
            url=doc4_url,
            content=raw_c4,
            content_hash=compute_content_hash(raw_c4, doc4_url),
            published_at=now - timedelta(days=2),
        )
        db.add(doc4)
        db.flush()

        ee4 = ExtractedEvent(
            document_id=doc4.id,
            event_type="regulatory_enforcement",
            event_title="SEC Enforcement Action",
            event_summary="SEC Enforcement Action",
            event_time=now - timedelta(days=2),
            location_entity_id=entities["Washington"].id,
            confidence=0.94,
            importance=0.62,
            metadata_={"extractor_version": "rule_based_v0.2.1", "entities": ["Securities and Exchange Commission"]},
        )
        db.add(ee4)
        db.flush()

        db.add(DocumentEntity(document_id=doc4.id, entity_id=entities["Securities and Exchange Commission"].id, mention_text="Securities and Exchange Commission", entity_role="regulator", confidence=0.97))
        db.add(EventClusterMember(
            event_cluster_id=c4.id,
            extracted_event_id=ee4.id,
            membership_score=1.0,
            membership_method="exact_seed",
            metadata_={},
        ))

        # Cluster 5: Event with MISSING Location and Time to test invariants (Requirement 14)
        c5 = EventCluster(
            canonical_title="Global Logistics Disruptions Reported Across Marine Transit Channels",
            canonical_summary="Widespread logistical backlogs noted with ambiguous timing and distributed locations.",
            event_type="market_crash",
            event_time_start=None,  # Intentionally null to test "Time unavailable"
            event_time_end=None,
            primary_location_entity_id=None,  # Intentionally null to test "Location unavailable"
            confidence=0.68,
            status="ACTIVE",
            metadata_={
                "importance": 0.45,
                "entities": [],
            }
        )
        db.add(c5)
        db.flush()

        raw_c5 = "Shipping bottlenecks reported on maritime cargo corridors."
        doc5_url = f"{sources['Reuters'].base_url}/news/{uuid.uuid4()}"
        doc5 = Document(
            source_id=sources["Reuters"].id,
            title="Global Freight Logistics Suffer Unscheduled Delays",
            url=doc5_url,
            content=raw_c5,
            content_hash=compute_content_hash(raw_c5, doc5_url),
            published_at=now - timedelta(days=5),
        )
        db.add(doc5)
        db.flush()

        ee5 = ExtractedEvent(
            document_id=doc5.id,
            event_type="market_crash",
            event_title="Freight Bottlenecks",
            event_summary="Freight Bottlenecks",
            event_time=None,
            location_entity_id=None,
            confidence=0.68,
            importance=0.45,
            metadata_={"extractor_version": "rule_based_v0.2.1", "entities": []},
        )
        db.add(ee5)
        db.flush()

        db.add(EventClusterMember(
            event_cluster_id=c5.id,
            extracted_event_id=ee5.id,
            membership_score=1.0,
            membership_method="exact_seed",
            metadata_={},
        ))

        db.commit()
        print("Successfully seeded realistic V0.4 verification intelligence into PostgreSQL.")
    except Exception as exc:
        db.rollback()
        print("Seeding error:", exc)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
