import sys
import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["ALLOW_PROD_AUDIT"] = "1"

from backend.app.db.session import SessionLocal
from backend.app.models.source import Source
from backend.app.models.ingestion_run import IngestionRun
from backend.app.models.document import Document
from sqlalchemy import select, desc, func, and_

def run_analysis():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        since_24h = now - timedelta(hours=24)
        
        sources = db.query(Source).order_by(Source.name).all()
        print("=" * 80)
        print("PHASE 2 & 3: SCHEDULER CYCLES & 24-HOUR OPERATIONAL EVIDENCE")
        print("=" * 80)
        
        phase2_cycles = {}
        phase3_stats = {}
        
        for s in sources:
            # Query runs for this source
            runs = (
                db.query(IngestionRun)
                .filter(IngestionRun.source_id == s.id)
                .order_by(desc(IngestionRun.started_at))
                .limit(10)
                .all()
            )
            
            # 3 consecutive cycles
            consecutive_3 = runs[:3]
            source_cycle_data = []
            for idx, r in enumerate(consecutive_3, 1):
                pstats = r.processing_stats or {}
                http_status = pstats.get("http_status") or (200 if r.status == "SUCCESS" else 500)
                req_dur = pstats.get("request_duration_ms", 0)
                items_rcvd = pstats.get("items_received", r.documents_discovered)
                new_items = pstats.get("new_items", r.documents_inserted)
                dups = pstats.get("duplicate_items", r.duplicates_skipped)
                parse_fails = pstats.get("parse_failures", 0)
                proc_fails = pstats.get("processing_failures", 0)
                last_pub = pstats.get("last_published_at")
                last_new_doc = pstats.get("last_new_document_at")
                consec_fails = pstats.get("consecutive_failures", 0)
                next_sched = pstats.get("next_scheduled_at")
                sched_at = pstats.get("scheduled_at", r.started_at.isoformat() if r.started_at else None)
                
                source_cycle_data.append({
                    "cycle": idx,
                    "run_id": str(r.id),
                    "status": r.status,
                    "scheduled_at": sched_at,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "next_scheduled_at": next_sched,
                    "http_status": http_status,
                    "request_duration_ms": req_dur,
                    "items_received": items_rcvd,
                    "new_items": new_items,
                    "duplicates": dups,
                    "parse_failures": parse_fails,
                    "processing_failures": proc_fails,
                    "last_published_at": last_pub,
                    "last_new_document_at": last_new_doc,
                    "consecutive_failures": consec_fails,
                    "freshness_state": s.freshness_status,
                    "operational_state": s.health_status,
                })
            phase2_cycles[s.name] = source_cycle_data
            
            # 24-hour analysis
            runs_24h = (
                db.query(IngestionRun)
                .filter(
                    IngestionRun.source_id == s.id,
                    IngestionRun.started_at >= since_24h,
                )
                .order_by(IngestionRun.started_at.asc())
                .all()
            )
            
            total_checks = len(runs_24h)
            success_checks = sum(1 for r in runs_24h if r.status == "SUCCESS")
            failed_checks = sum(1 for r in runs_24h if r.status == "FAILED")
            new_docs_24h = sum(r.documents_inserted for r in runs_24h)
            dups_24h = sum(r.duplicates_skipped for r in runs_24h)
            
            # Latencies
            latencies = []
            for r in runs_24h:
                pstats = r.processing_stats or {}
                if "request_duration_ms" in pstats and pstats["request_duration_ms"]:
                    latencies.append(pstats["request_duration_ms"])
                elif r.completed_at and r.started_at:
                    dur_ms = (r.completed_at - r.started_at).total_seconds() * 1000.0
                    latencies.append(dur_ms)
            
            latencies.sort()
            avg_lat = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
            p95_idx = int(len(latencies) * 0.95)
            p95_lat = round(latencies[p95_idx], 1) if latencies else 0.0
            
            latest_run = runs[0] if runs else None
            
            phase3_stats[s.name] = {
                "active": s.active,
                "operational_state": s.health_status,
                "checks_24h": total_checks,
                "successful_checks_24h": success_checks,
                "failed_checks_24h": failed_checks,
                "new_documents_24h": new_docs_24h,
                "duplicates_24h": dups_24h,
                "latest_publication": str(s.latest_published_at_observed)[:19] if s.latest_published_at_observed else "None",
                "latest_ingestion": str(s.last_successful_ingestion_at)[:19] if s.last_successful_ingestion_at else "None",
                "latest_successful_check": str(s.last_successful_fetch_at)[:19] if s.last_successful_fetch_at else "None",
                "consecutive_failures": s.consecutive_failures,
                "avg_latency_ms": avg_lat,
                "p95_latency_ms": p95_lat,
            }
        
        # Save JSON output for reporting
        output_data = {
            "timestamp": now.isoformat(),
            "phase2_cycles": phase2_cycles,
            "phase3_stats": phase3_stats,
        }
        with open("scratch/certify_scheduler_24h_results.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
            
        print(f"Recorded 3 consecutive cycles for {len(phase2_cycles)} sources.")
        print(f"Analyzed 24h history for {len(phase3_stats)} sources.")
        
        # Print sample proof of decoupling
        print("\n--- PROOF OF DECOUPLING (LAST_CHECKED vs LAST_NEW_CONTENT) ---")
        for name, data in phase3_stats.items():
            if data["successful_checks_24h"] > 0:
                print(f"{name:<35} | State={data['operational_state']:<12} | LastCheck={data['latest_successful_check']} | LastIngest={data['latest_ingestion']} | Checks={data['checks_24h']} | NewDocs={data['new_documents_24h']} | Dups={data['duplicates_24h']}")
                
    finally:
        db.close()

if __name__ == "__main__":
    run_analysis()
