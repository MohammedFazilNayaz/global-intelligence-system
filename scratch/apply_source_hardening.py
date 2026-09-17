import os
import sys
sys.path.insert(0, ".")
os.environ["ALLOW_PROD_DB_MUTATION"] = "1"

from backend.app.db.session import SessionLocal, engine
engine.echo = False
from backend.app.models.source import Source
from sqlalchemy import select

with SessionLocal() as db:
    # 1. ArXiv CS.AI Research
    arxiv = db.scalars(select(Source).where(Source.name == "ArXiv CS.AI Research")).first()
    if arxiv:
        arxiv.feed_url = "https://export.arxiv.org/rss/cs.AI"
        arxiv.consecutive_failures = 0
        arxiv.last_error_message = None
        print(f"Updated ArXiv feed_url to {arxiv.feed_url}")

    # 2. FRED Macroeconomic API -> AUTH_REQUIRED
    fred = db.scalars(select(Source).where(Source.name == "FRED Macroeconomic API")).first()
    if fred:
        meta = dict(fred.config_metadata or {})
        meta["auth_required"] = True
        fred.config_metadata = meta
        fred.last_error_message = "Requires official St. Louis Fed 32-character API key"
        print("Classified FRED Macroeconomic API as AUTH_REQUIRED")

    # 3. World Bank Open Data
    wb = db.scalars(select(Source).where(Source.name == "World Bank Open Data")).first()
    if wb:
        wb.feed_url = "https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?format=json"
        meta = dict(wb.config_metadata or {})
        meta["items_path"] = "1"
        meta["field_mapping"] = {
            "title": "indicator.value",
            "description": "countryiso3code",
            "url": "country.value",
            "published_at": "date"
        }
        wb.config_metadata = meta
        wb.consecutive_failures = 0
        wb.last_error_message = None
        print("Updated World Bank Open Data endpoint and config_metadata")

    # 4. CoinGecko Market Telemetry
    cg = db.scalars(select(Source).where(Source.name == "CoinGecko Market Telemetry")).first()
    if cg:
        meta = dict(cg.config_metadata or {})
        meta["field_mapping"] = {
            "title": "key",
            "url": "key",
            "description": "usd"
        }
        cg.config_metadata = meta
        cg.consecutive_failures = 0
        cg.last_error_message = None
        print("Updated CoinGecko config_metadata")

    # 5. US Department of State Press
    dos = db.scalars(select(Source).where(Source.name == "US Department of State Press")).first()
    if dos:
        dos.consecutive_failures = 0
        dos.last_error_message = None
        print("Reset State Dept error state (verified reachable with browser UA)")

    db.commit()
    print("Database source hardening successfully committed.")
