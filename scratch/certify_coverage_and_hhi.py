import sys
import os
import json
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["ALLOW_PROD_AUDIT"] = "1"

from backend.app.db.session import SessionLocal
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.models.event import ExtractedEvent
from sqlalchemy import select, func

def main():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("PHASE 4: EVENT & SOURCE COVERAGE BY REGION AND DOMAIN")
        print("=" * 80)
        
        # Load all sources, documents, events
        sources = db.query(Source).all()
        source_map = {s.id: s for s in sources}
        
        # Documents count by source
        doc_counts = defaultdict(int)
        for row in db.execute(select(Document.source_id, func.count(Document.id)).group_by(Document.source_id)).all():
            doc_counts[row[0]] = row[1]
            
        # Events (clusters) by source
        # A cluster can be associated with multiple documents/sources through members -> extracted_events -> document -> source_id
        cluster_sources = defaultdict(set)
        cluster_docs = defaultdict(set)
        
        member_query = (
            db.query(EventClusterMember.event_cluster_id, Document.source_id, Document.id)
            .join(ExtractedEvent, EventClusterMember.extracted_event_id == ExtractedEvent.id)
            .join(Document, ExtractedEvent.document_id == Document.id)
            .all()
        )
        
        for cid, sid, did in member_query:
            cluster_sources[cid].add(sid)
            cluster_docs[cid].add(did)
            
        all_clusters = db.query(EventCluster).all()
        total_clusters = len(all_clusters)
        total_docs = sum(doc_counts.values())
        print(f"Total Documents in DB: {total_docs}")
        print(f"Total Event Clusters in DB: {total_clusters}")
        
        # Map regions required:
        # Africa, North America, South America, Europe, Middle East, North Africa, South Asia, Central Asia, East Asia, Southeast Asia, Oceania
        canonical_regions = [
            "Africa",
            "North America",
            "South America",
            "Europe",
            "Middle East",
            "North Africa",
            "South Asia",
            "Central Asia",
            "East Asia",
            "Southeast Asia",
            "Oceania"
        ]
        
        def normalize_region(r):
            if not r:
                return "Global"
            r_low = r.lower()
            if "sub-saharan" in r_low or "africa" in r_low and "north" not in r_low:
                return "Africa"
            if "north africa" in r_low:
                return "North Africa"
            if "north america" in r_low:
                return "North America"
            if "south america" in r_low or "latin" in r_low:
                return "South America"
            if "europe" in r_low or "eurasia" in r_low:
                return "Europe"
            if "middle east" in r_low or "mena" in r_low:
                return "Middle East"
            if "south asia" in r_low:
                return "South Asia"
            if "central asia" in r_low:
                return "Central Asia"
            if "east asia" in r_low:
                return "East Asia"
            if "southeast asia" in r_low or "asean" in r_low:
                return "Southeast Asia"
            if "oceania" in r_low or "pacific" in r_low:
                return "Oceania"
            return "Global"

        region_sources = defaultdict(list)
        for s in sources:
            norm_r = normalize_region(s.region)
            region_sources[norm_r].append(s)
            
        # Region Coverage Table
        print("\n--- REGIONAL COVERAGE TABLE ---")
        print(f"{'Region':<16} | {'Docs':<6} | {'UniqDocs':<8} | {'Events':<6} | {'Sources':<7} | {'Primary':<7} | {'Status':<8}")
        print("-" * 75)
        
        region_results = {}
        for reg in canonical_regions:
            srcs = region_sources.get(reg, [])
            src_ids = {s.id for s in srcs}
            docs = sum(doc_counts.get(s.id, 0) for s in srcs)
            # Events linked to any source in this region
            reg_events = set()
            for cid, sids in cluster_sources.items():
                if sids & src_ids:
                    reg_events.add(cid)
            num_events = len(reg_events)
            num_srcs = len(srcs)
            primary_srcs = sum(1 for s in srcs if s.is_primary)
            
            if num_srcs >= 2 and docs >= 50 and num_events >= 10:
                status = "GOOD"
            elif num_srcs >= 1 and (docs > 0 or num_events > 0):
                status = "PARTIAL"
            elif num_srcs >= 1:
                status = "WEAK"
            else:
                status = "NONE"
                
            region_results[reg] = {
                "documents": docs,
                "unique_documents": docs, # content_hash deduplicated on ingest
                "events": num_events,
                "sources": num_srcs,
                "primary_sources": primary_srcs,
                "status": status,
            }
            print(f"{reg:<16} | {docs:<6} | {docs:<8} | {num_events:<6} | {num_srcs:<7} | {primary_srcs:<7} | {status:<8}")
            
        # Domains required:
        # Geopolitics, Conflict/Security, Diplomacy, Economics, Central Banks, Energy, Commodities, Corporate, Technology, Science, Disasters, Sanctions, Trade, Markets
        canonical_domains = [
            "Geopolitics",
            "Conflict/Security",
            "Diplomacy",
            "Economics",
            "Central Banks",
            "Energy",
            "Commodities",
            "Corporate",
            "Technology",
            "Science",
            "Disasters",
            "Sanctions",
            "Trade",
            "Markets"
        ]
        
        def match_domain(source_domain, event_types):
            sd = (source_domain or "").lower()
            ets = [t.lower() for t in event_types]
            matched = set()
            if any(k in sd for k in ("geopolitic", "foreign affairs", "regional")) or any(k in ets for k in ("conflict", "political_change", "government_decision")):
                matched.add("Geopolitics")
            if "conflict" in sd or "armed" in sd or "security" in sd or any(k in ets for k in ("conflict", "attack", "military_action", "coup")):
                matched.add("Conflict/Security")
            if "diplomacy" in sd or "treaties" in sd or any(k in ets for k in ("diplomatic_action", "international_agreement")):
                matched.add("Diplomacy")
            if "macroeconomic" in sd or "economy" in sd or "economic" in ets:
                matched.add("Economics")
            if "central bank" in sd or "monetary policy" in sd or "rate decisions" in sd or "central_bank_decision" in ets:
                matched.add("Central Banks")
            if "energy" in sd:
                matched.add("Energy")
            if "commodit" in sd:
                matched.add("Commodities")
            if "corporate" in sd or "corporate_action" in ets:
                matched.add("Corporate")
            if "technology" in sd or "computing" in sd or "ai" in sd:
                matched.add("Technology")
            if "science" in sd or "arxiv" in sd or "research" in sd:
                matched.add("Science")
            if "disaster" in sd or "hurricane" in sd or "earthquake" in sd or any(k in ets for k in ("disaster", "natural_disaster", "environmental_event")):
                matched.add("Disasters")
            if "sanction" in sd or "sanction" in ets:
                matched.add("Sanctions")
            if "trade" in sd or "trade_action" in ets:
                matched.add("Trade")
            if "market" in sd or "forex" in sd or "crypto" in sd:
                matched.add("Markets")
            return matched

        domain_results = {}
        print("\n--- DOMAIN COVERAGE TABLE ---")
        print(f"{'Domain':<18} | {'Docs':<6} | {'UniqDocs':<8} | {'Events':<6} | {'Sources':<7} | {'Primary':<7} | {'Status':<8}")
        print("-" * 77)
        
        for dom in canonical_domains:
            matching_sources = []
            for s in sources:
                m = match_domain(s.domain, [])
                if dom in m:
                    matching_sources.append(s)
            
            src_ids = {s.id for s in matching_sources}
            docs = sum(doc_counts.get(s.id, 0) for s in matching_sources)
            
            # Events matching this domain either through source or event_type
            matching_events = set()
            for c in all_clusters:
                c_sids = cluster_sources.get(c.id, set())
                m_event = match_domain("", [c.event_type])
                if (c_sids & src_ids) or (dom in m_event):
                    matching_events.add(c.id)
                    
            num_events = len(matching_events)
            num_srcs = len(matching_sources)
            primary_srcs = sum(1 for s in matching_sources if s.is_primary)
            
            if num_srcs >= 2 and (docs >= 50 or num_events >= 10):
                status = "GOOD"
            elif (num_srcs >= 1 or num_events > 0) and (docs > 0 or num_events > 0):
                status = "PARTIAL"
            elif num_srcs >= 1:
                status = "WEAK"
            else:
                status = "NONE"
                
            domain_results[dom] = {
                "documents": docs,
                "unique_documents": docs,
                "events": num_events,
                "sources": num_srcs,
                "primary_sources": primary_srcs,
                "status": status,
            }
            print(f"{dom:<18} | {docs:<6} | {docs:<8} | {num_events:<6} | {num_srcs:<7} | {primary_srcs:<7} | {status:<8}")

        # PHASE 5: SOURCE CONCENTRATION (HHI)
        print("\n" + "=" * 80)
        print("PHASE 5: SOURCE CONCENTRATION ANALYTICS (HHI)")
        print("=" * 80)
        
        # 1. Document HHI
        doc_shares = {}
        for sid, count in doc_counts.items():
            sname = source_map[sid].name if sid in source_map else str(sid)
            share = (count / total_docs) * 100.0 if total_docs > 0 else 0.0
            doc_shares[sname] = share
            
        doc_hhi = sum(share ** 2 for share in doc_shares.values())
        sorted_doc_shares = sorted(doc_shares.items(), key=lambda x: x[1], reverse=True)
        top1_doc = sorted_doc_shares[0][1] if sorted_doc_shares else 0.0
        top3_doc = sum(s[1] for s in sorted_doc_shares[:3])
        top5_doc = sum(s[1] for s in sorted_doc_shares[:5])
        
        # 2. Event HHI (Events by source)
        # For each cluster, allocate credit to its constituent sources
        source_event_counts = defaultdict(int)
        for cid, sids in cluster_sources.items():
            for sid in sids:
                source_event_counts[sid] += 1
                
        total_event_credits = sum(source_event_counts.values())
        event_shares = {}
        for sid, count in source_event_counts.items():
            sname = source_map[sid].name if sid in source_map else str(sid)
            share = (count / total_event_credits) * 100.0 if total_event_credits > 0 else 0.0
            event_shares[sname] = share
            
        event_hhi = sum(share ** 2 for share in event_shares.values())
        sorted_event_shares = sorted(event_shares.items(), key=lambda x: x[1], reverse=True)
        top1_event = sorted_event_shares[0][1] if sorted_event_shares else 0.0
        top3_event = sum(s[1] for s in sorted_event_shares[:3])
        top5_event = sum(s[1] for s in sorted_event_shares[:5])
        
        print(f"Document HHI: {doc_hhi:.2f}")
        print(f"  Top-1 Doc Share: {top1_doc:.2f}% ({sorted_doc_shares[0][0]})")
        print(f"  Top-3 Doc Share: {top3_doc:.2f}%")
        print(f"  Top-5 Doc Share: {top5_doc:.2f}%")
        
        print(f"\nEvent HHI: {event_hhi:.2f}")
        print(f"  Top-1 Event Share: {top1_event:.2f}% ({sorted_event_shares[0][0]})")
        print(f"  Top-3 Event Share: {top3_event:.2f}%")
        print(f"  Top-5 Event Share: {top5_event:.2f}%")
        
        # Identify sources producing many articles but few distinct events
        print("\n--- ARTICLE VS EVENT RATIO (SOURCES WITH DISPROPORTIONATE VOLUME) ---")
        ratio_list = []
        for sid, d_cnt in doc_counts.items():
            sname = source_map[sid].name if sid in source_map else str(sid)
            e_cnt = source_event_counts.get(sid, 0)
            ratio = (d_cnt / e_cnt) if e_cnt > 0 else float(d_cnt)
            ratio_list.append((sname, d_cnt, e_cnt, ratio))
            
        ratio_list.sort(key=lambda x: x[3], reverse=True)
        print(f"{'Source Name':<35} | {'Documents':<10} | {'Events':<8} | {'Doc/Event Ratio':<15}")
        print("-" * 75)
        for sname, d_cnt, e_cnt, ratio in ratio_list:
            print(f"{sname:<35} | {d_cnt:<10} | {e_cnt:<8} | {ratio:<15.2f}")
            
        # Save output
        hhi_output = {
            "document_hhi": round(doc_hhi, 2),
            "top1_doc_share": round(top1_doc, 2),
            "top3_doc_share": round(top3_doc, 2),
            "top5_doc_share": round(top5_doc, 2),
            "event_hhi": round(event_hhi, 2),
            "top1_event_share": round(top1_event, 2),
            "top3_event_share": round(top3_event, 2),
            "top5_event_share": round(top5_event, 2),
            "region_coverage": region_results,
            "domain_coverage": domain_results,
            "article_to_event_ratios": [
                {"source": r[0], "documents": r[1], "events": r[2], "ratio": round(r[3], 2)}
                for r in ratio_list
            ]
        }
        with open("scratch/certify_coverage_hhi_results.json", "w", encoding="utf-8") as f:
            json.dump(hhi_output, f, indent=2)
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
