import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["ALLOW_PROD_AUDIT"] = "1"

from backend.app.db.session import SessionLocal
from backend.app.models.event import ExtractedEvent
from backend.app.services.dossier_service import build_event_intelligence_dossier
from backend.app.schemas.dossier import EvidenceClass

REQUIRED_21_FIELDS = [
    "what_happened",
    "why_it_matters",
    "directly_involved",
    "directly_affected",
    "potential_beneficiaries",
    "potential_exposures",
    "affected_countries",
    "affected_companies",
    "affected_sectors",
    "commodity_connections",
    "currency_connections",
    "equity_connections",
    "rate_connections",
    "economic_indicators",
    "geopolitical_connections",
    "related_events",
    "related_entities",
    "market_observations",
    "source_evidence",
    "confidence",
    "last_updated",
]

def main():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("PHASE 6 & 7: DOSSIER QUALITY & FACT/ANALYSIS SEPARATION AUDIT")
        print("=" * 80)
        
        # Select 20 distinct real production events across event types
        events = (
            db.query(ExtractedEvent)
            .order_by(ExtractedEvent.event_time.desc().nullslast())
            .all()
        )
        
        selected_events = []
        types_seen = {}
        for e in events:
            cnt = types_seen.get(e.event_type, 0)
            if cnt < 3: # take up to 3 per event type to ensure broad diversity
                selected_events.append(e)
                types_seen[e.event_type] = cnt + 1
            if len(selected_events) >= 20:
                break
                
        print(f"Selected {len(selected_events)} production events across {len(types_seen)} event types.")
        
        audit_results = []
        evidence_class_counts = {ec.value: 0 for ec in EvidenceClass}
        
        for idx, event in enumerate(selected_events, 1):
            dossier = build_event_intelligence_dossier(db, event.id)
            if not dossier:
                print(f"[{idx}] FAILED to build dossier for {event.id}")
                continue
                
            d_dict = dossier.model_dump()
            
            # 1. Verify 21 fields
            missing_fields = [f for f in REQUIRED_21_FIELDS if f not in d_dict]
            
            # 2. Count evidence classes across all relationships & impacts
            event_classes = []
            
            # countries
            for c_impact in dossier.affected_countries:
                if c_impact.evidence_class:
                    ev = c_impact.evidence_class.value
                    evidence_class_counts[ev] += 1
                    event_classes.append(ev)
                    
            # companies
            for comp_impact in dossier.affected_companies:
                if comp_impact.evidence_class:
                    ev = comp_impact.evidence_class.value
                    evidence_class_counts[ev] += 1
                    event_classes.append(ev)
                    
            # sectors
            for sec_impact in dossier.affected_sectors:
                if sec_impact.evidence_class:
                    ev = sec_impact.evidence_class.value
                    evidence_class_counts[ev] += 1
                    event_classes.append(ev)
                    
            # market connections (commodities, currencies, equities, rates)
            for m_list in (dossier.commodity_connections, dossier.currency_connections, dossier.equity_connections, dossier.rate_connections):
                for mc in m_list:
                    if mc.evidence_class:
                        ev = mc.evidence_class.value
                        evidence_class_counts[ev] += 1
                        event_classes.append(ev)
                        
            # geopolitical connections
            for geo in dossier.geopolitical_connections:
                if geo.evidence_class:
                    ev = geo.evidence_class.value
                    evidence_class_counts[ev] += 1
                    event_classes.append(ev)
                    
            # related events
            for re in dossier.related_events:
                if re.evidence_class:
                    ev = re.evidence_class.value
                    evidence_class_counts[ev] += 1
                    event_classes.append(ev)
                    
            # related entities
            for rent in dossier.related_entities:
                if rent.evidence_class:
                    ev = rent.evidence_class.value
                    evidence_class_counts[ev] += 1
                    event_classes.append(ev)
                    
            # source evidence
            for se in dossier.source_evidence:
                if se.evidence_class:
                    ev = se.evidence_class.value
                    evidence_class_counts[ev] += 1
                    event_classes.append(ev)
                    
            record = {
                "event_id": str(event.id),
                "title": event.event_title,
                "event_type": event.event_type,
                "confidence": dossier.confidence,
                "missing_fields": missing_fields,
                "directly_involved_count": len(dossier.directly_involved),
                "directly_affected_count": len(dossier.directly_affected),
                "countries_count": len(dossier.affected_countries),
                "companies_count": len(dossier.affected_companies),
                "sectors_count": len(dossier.affected_sectors),
                "geopolitical_count": len(dossier.geopolitical_connections),
                "sources_count": len(dossier.source_evidence),
                "has_what_happened": bool(dossier.what_happened),
                "has_why_it_matters": bool(dossier.why_it_matters),
                "evidence_classes_present": list(set(event_classes)),
                "timestamps": {
                    "publication_time": str(dossier.publication_time),
                    "fetch_time": str(dossier.fetch_time),
                    "ingestion_time": str(dossier.ingestion_time),
                    "extraction_time": str(dossier.extraction_time),
                    "intelligence_update_time": str(dossier.intelligence_update_time),
                }
            }
            audit_results.append(record)
            
            print(f"[{idx:02d}] {event.event_type:<18} | {event.event_title[:45]:<45} | MissingFields={len(missing_fields)} | Sources={len(dossier.source_evidence)} | Sectors={len(dossier.affected_sectors)} | Countries={len(dossier.affected_countries)}")
            
        print("\n--- EVIDENCE CLASS FREQUENCY DISTRIBUTION ---")
        for ev, cnt in evidence_class_counts.items():
            print(f"  {ev:<25}: {cnt}")
            
        with open("scratch/certify_dossier_quality_results.json", "w", encoding="utf-8") as f:
            json.dump({
                "events_tested": len(audit_results),
                "evidence_class_distribution": evidence_class_counts,
                "audit_results": audit_results,
            }, f, indent=2)
            
        print(f"\nSaved detailed audit results for {len(audit_results)} events to scratch/certify_dossier_quality_results.json.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
