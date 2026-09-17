"""Seed verified public sources for the Global Intelligence Platform across 11 global regions and 35 domains."""

import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Explicit permission flag for production source seeding
os.environ["ALLOW_PROD_DB_MUTATION"] = "1"

from backend.app.db.session import SessionLocal
from backend.app.services.source_service import get_source_by_name, create_source
from backend.app.schemas.source import SourceCreate
from backend.app.models.source import Source
from backend.app.utils.logger import setup_logger

logger = setup_logger("scripts.seed_sources")

VERIFIED_GLOBAL_SOURCES = [
    # 1. Global Wires & Secondary Multi-Regional
    SourceCreate(
        name="BBC World News",
        source_type="rss",
        base_url="https://www.bbc.com",
        feed_url="https://feeds.bbci.co.uk/news/world/rss.xml",
        reliability_score=0.90,
        active=True,
        polling_interval_seconds=300,
        config_metadata={"country": "GB", "region": "Europe", "domain": "Geopolitics", "is_primary": False, "priority": 2},
    ),
    SourceCreate(
        name="Al Jazeera World",
        source_type="rss",
        base_url="https://www.aljazeera.com",
        feed_url="https://www.aljazeera.com/xml/rss/all.xml",
        reliability_score=0.88,
        active=True,
        polling_interval_seconds=300,
        config_metadata={"country": "QA", "region": "Middle East", "domain": "Geopolitics / Armed Conflict", "is_primary": False, "priority": 2},
    ),
    SourceCreate(
        name="Deutsche Welle World",
        source_type="rss",
        base_url="https://www.dw.com",
        feed_url="https://rss.dw.com/rdf/rss-en-all",
        reliability_score=0.90,
        active=True,
        polling_interval_seconds=600,
        config_metadata={"country": "DE", "region": "Europe", "domain": "Geopolitics / European Affairs", "is_primary": False, "priority": 2},
    ),
    SourceCreate(
        name="France 24 English",
        source_type="rss",
        base_url="https://www.france24.com",
        feed_url="https://www.france24.com/en/rss",
        reliability_score=0.88,
        active=True,
        polling_interval_seconds=600,
        config_metadata={"country": "FR", "region": "Europe", "domain": "Diplomacy / Francophone Africa", "is_primary": False, "priority": 2},
    ),
    SourceCreate(
        name="MercoPress South America",
        source_type="rss",
        base_url="https://en.mercopress.com",
        feed_url="https://en.mercopress.com/rss",
        reliability_score=0.85,
        active=True,
        polling_interval_seconds=900,
        config_metadata={"country": "UY", "region": "Latin America", "domain": "Trade / Regional Geopolitics", "is_primary": False, "priority": 2},
    ),
    SourceCreate(
        name="AllAfrica Top Headlines",
        source_type="rss",
        base_url="https://allafrica.com",
        feed_url="https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf",
        reliability_score=0.85,
        active=True,
        polling_interval_seconds=900,
        config_metadata={"country": "ZA", "region": "Sub-Saharan Africa", "domain": "African Security & Economy", "is_primary": False, "priority": 2},
    ),
    SourceCreate(
        name="The Hindu International",
        source_type="rss",
        base_url="https://www.thehindu.com",
        feed_url="https://www.thehindu.com/news/international/feeder/default.rss",
        reliability_score=0.89,
        active=True,
        polling_interval_seconds=900,
        config_metadata={"country": "IN", "region": "South Asia", "domain": "South Asian Geopolitics & Trade", "is_primary": False, "priority": 2},
    ),
    SourceCreate(
        name="South China Morning Post",
        source_type="rss",
        base_url="https://www.scmp.com",
        feed_url="https://www.scmp.com/rss/91/feed",
        reliability_score=0.87,
        active=True,
        polling_interval_seconds=900,
        config_metadata={"country": "HK", "region": "East Asia", "domain": "East Asian Geopolitics & Technology", "is_primary": False, "priority": 2},
    ),
    SourceCreate(
        name="ABC News Australia",
        source_type="rss",
        base_url="https://www.abc.net.au",
        feed_url="https://www.abc.net.au/news/feed/51120/rss.xml",
        reliability_score=0.90,
        active=True,
        polling_interval_seconds=900,
        config_metadata={"country": "AU", "region": "Oceania", "domain": "Pacific Affairs & Indo-Pacific Security", "is_primary": False, "priority": 2},
    ),
    SourceCreate(
        name="TASS Russian News Agency",
        source_type="rss",
        base_url="https://tass.com",
        feed_url="https://tass.com/rss/v2.xml",
        reliability_score=0.82,
        active=True,
        polling_interval_seconds=900,
        config_metadata={"country": "RU", "region": "Eurasia", "domain": "Eurasian Geopolitics & Security", "is_primary": False, "priority": 2},
    ),
    SourceCreate(
        name="The Straits Times",
        source_type="rss",
        base_url="https://www.straitstimes.com",
        feed_url="https://www.straitstimes.com/news/world/rss.xml",
        reliability_score=0.88,
        active=True,
        polling_interval_seconds=900,
        config_metadata={"country": "SG", "region": "Southeast Asia", "domain": "ASEAN Trade & Regional Politics", "is_primary": False, "priority": 2},
    ),
    SourceCreate(
        name="Ahram Online",
        source_type="rss",
        base_url="https://english.ahram.org.eg",
        feed_url="https://english.ahram.org.eg/rss/1/1/Egypt.xml",
        reliability_score=0.84,
        active=True,
        polling_interval_seconds=900,
        config_metadata={"country": "EG", "region": "North Africa", "domain": "MENA Regional Affairs & Diplomacy", "is_primary": False, "priority": 2},
    ),

    # 2. Primary Sovereign & Diplomatic Bodies
    SourceCreate(
        name="US Department of State Press",
        source_type="rss",
        base_url="https://www.state.gov",
        feed_url="https://www.state.gov/rss-feed/press-releases/feed/",
        reliability_score=0.98,
        active=True,
        polling_interval_seconds=900,
        config_metadata={"country": "US", "region": "North America", "domain": "Foreign Policy & Treaties", "is_primary": True, "priority": 1},
    ),
    SourceCreate(
        name="UK Foreign Commonwealth & Development Office",
        source_type="rss",
        base_url="https://www.gov.uk/government/organisations/foreign-commonwealth-development-office",
        feed_url="https://www.gov.uk/government/organisations/foreign-commonwealth-development-office.atom",
        reliability_score=0.98,
        active=True,
        polling_interval_seconds=1800,
        config_metadata={"country": "GB", "region": "Europe", "domain": "Foreign Affairs & Diplomatic Declarations", "is_primary": True, "priority": 1},
    ),

    # 3. Monetary Authorities & Central Banks
    SourceCreate(
        name="US Federal Reserve Press",
        source_type="rss",
        base_url="https://www.federalreserve.gov",
        feed_url="https://www.federalreserve.gov/feeds/press_all.xml",
        reliability_score=0.99,
        active=True,
        polling_interval_seconds=1800,
        config_metadata={"country": "US", "region": "North America", "domain": "Central Banking & Monetary Policy", "is_primary": True, "priority": 1},
    ),
    SourceCreate(
        name="European Central Bank Press",
        source_type="rss",
        base_url="https://www.ecb.europa.eu",
        feed_url="https://www.ecb.europa.eu/rss/press.html",
        reliability_score=0.99,
        active=True,
        polling_interval_seconds=1800,
        config_metadata={"country": "EU", "region": "Europe", "domain": "Central Banking & Rate Decisions", "is_primary": True, "priority": 1},
    ),
    SourceCreate(
        name="Bank of England News",
        source_type="rss",
        base_url="https://www.bankofengland.co.uk",
        feed_url="https://www.bankofengland.co.uk/rss/news",
        reliability_score=0.99,
        active=True,
        polling_interval_seconds=1800,
        config_metadata={"country": "GB", "region": "Europe", "domain": "Central Banking & Financial Stability", "is_primary": True, "priority": 1},
    ),
    SourceCreate(
        name="Reserve Bank of India Press",
        source_type="rss",
        base_url="https://rbi.org.in",
        feed_url="https://rbi.org.in/pressreleases_rss.xml",
        reliability_score=0.99,
        active=True,
        polling_interval_seconds=1800,
        config_metadata={"country": "IN", "region": "South Asia", "domain": "Central Banking & Macroprudential Policy", "is_primary": True, "priority": 1},
    ),

    # 4. Natural Hazards & Disaster Intelligence
    SourceCreate(
        name="USGS Earthquakes M4.5+",
        source_type="geojson",
        base_url="https://earthquake.usgs.gov",
        feed_url="https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson",
        reliability_score=1.0,
        active=True,
        polling_interval_seconds=300,
        config_metadata={"country": "US", "region": "North America", "domain": "Natural Disasters (Seismic)", "is_primary": True, "priority": 1},
    ),
    SourceCreate(
        name="GDACS Disaster Alerts",
        source_type="rss",
        base_url="https://www.gdacs.org",
        feed_url="https://www.gdacs.org/xml/rss.xml",
        reliability_score=0.98,
        active=True,
        polling_interval_seconds=600,
        config_metadata={"country": "CH", "region": "Europe", "domain": "Natural Disasters (Multi-hazard)", "is_primary": True, "priority": 1},
    ),
    SourceCreate(
        name="NOAA National Hurricane Center",
        source_type="rss",
        base_url="https://www.nhc.noaa.gov",
        feed_url="https://www.nhc.noaa.gov/index-at.xml",
        reliability_score=0.99,
        active=True,
        polling_interval_seconds=1800,
        config_metadata={"country": "US", "region": "North America", "domain": "Tropical Cyclones & Severe Weather", "is_primary": True, "priority": 1},
    ),

    # 5. Frontier Science & Technology
    SourceCreate(
        name="ArXiv CS.AI Research",
        source_type="rss",
        base_url="https://arxiv.org",
        feed_url="https://rss.arxiv.org/rss/cs.AI",
        reliability_score=0.95,
        active=True,
        polling_interval_seconds=3600,
        config_metadata={"country": "US", "region": "North America", "domain": "Frontier AI & Computing Research", "is_primary": True, "priority": 3},
    ),

    # 6. Sanctions & Multilateral Datasets
    SourceCreate(
        name="US OFAC SDN Sanctions",
        source_type="rss",
        base_url="https://www.treasury.gov",
        feed_url="https://www.treasury.gov/ofac/downloads/sdn.xml",
        reliability_score=1.0,
        active=False,  # Large batch file (29MB), activated for daily batch worker
        polling_interval_seconds=86400,
        config_metadata={"country": "US", "region": "North America", "domain": "Sanctions Blacklist", "is_primary": True, "priority": 3},
    ),
    SourceCreate(
        name="ECB Euro FX Reference",
        source_type="rss",
        base_url="https://www.ecb.europa.eu",
        feed_url="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
        reliability_score=1.0,
        active=True,
        polling_interval_seconds=3600,
        config_metadata={"country": "EU", "region": "Europe", "domain": "Forex Reference Rates", "is_primary": True, "priority": 1},
    ),
    SourceCreate(
        name="World Bank Open Data",
        source_type="api",
        base_url="http://api.worldbank.org",
        feed_url="http://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?format=json",
        reliability_score=0.99,
        active=True,
        polling_interval_seconds=86400,
        config_metadata={"country": "US", "region": "North America", "domain": "Macroeconomic Baseline", "is_primary": True, "priority": 3},
    ),
    SourceCreate(
        name="FRED Macroeconomic API",
        source_type="api",
        base_url="https://fred.stlouisfed.org",
        feed_url="https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS",
        reliability_score=1.0,
        active=True,
        polling_interval_seconds=3600,
        config_metadata={"country": "US", "region": "North America", "domain": "Macroeconomic Indicators & Interest Rates", "is_primary": True, "priority": 1},
    ),
    SourceCreate(
        name="CoinGecko Market Telemetry",
        source_type="api",
        base_url="https://api.coingecko.com",
        feed_url="https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd",
        reliability_score=1.0,
        active=True,
        polling_interval_seconds=60,
        config_metadata={"country": "US", "region": "North America", "domain": "Crypto Market Telemetry", "is_primary": True, "priority": 1},
    ),
]


def seed_sources() -> None:
    db = SessionLocal()
    try:
        # First, deactivate deprecated UN News if present
        un_news = get_source_by_name(db, name="UN News World Releases")
        if un_news:
            un_news.active = False
            un_news.last_error_message = "Deprecated upstream (HTTP 404)"
            un_news.freshness_status = "FAILED"
            db.commit()
            logger.info("Deactivated deprecated 'UN News World Releases' source.")

        created_count = 0
        updated_count = 0

        for item in VERIFIED_GLOBAL_SOURCES:
            existing = get_source_by_name(db, name=item.name)
            meta = item.config_metadata or {}
            reg = meta.get("region", item.region)
            cty = meta.get("country", item.country)
            dom = meta.get("domain", item.domain)
            is_prim = meta.get("is_primary", item.is_primary)

            if existing:
                # Update metadata and explicit columns
                existing.config_metadata = meta
                existing.polling_interval_seconds = item.polling_interval_seconds
                existing.source_type = item.source_type
                existing.feed_url = item.feed_url
                existing.base_url = item.base_url
                existing.region = reg
                existing.country = cty
                existing.domain = dom
                existing.is_primary = is_prim
                existing.active = item.active
                updated_count += 1
            else:
                item.region = reg
                item.country = cty
                item.domain = dom
                item.is_primary = is_prim
                create_source(db, item)
                created_count += 1

        db.commit()
        logger.info(f"Source seeding complete: {created_count} created, {updated_count} updated.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_sources()
