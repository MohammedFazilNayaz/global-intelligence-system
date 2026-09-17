import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["ALLOW_PROD_AUDIT"] = "1"

from backend.app.db.session import SessionLocal
from backend.app.models.source import Source

def main():
    db = SessionLocal()
    try:
        sources = db.query(Source).order_by(Source.name).all()
        print(f"Total sources in DB: {len(sources)}")
        states_count = {}
        for s in sources:
            health = s.health_status
            states_count[health] = states_count.get(health, 0) + 1
            print(f"ID={str(s.id)[:8]} | Name={s.name:<33} | Type={s.source_type:<8} | Active={str(s.active):<5} | Failures={s.consecutive_failures} | Freshness={s.freshness_status:<10} | Health={health:<15} | LastFetched={str(s.last_successful_fetch_at)[:19]}")
        
        print("\nSummary by Operational State / Health:")
        for k, v in sorted(states_count.items()):
            print(f"  {k}: {v}")
        print(f"Total: {sum(states_count.values())}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
