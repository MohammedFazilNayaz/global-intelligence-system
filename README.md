# Global Intelligence Platform — V0.2 Intelligence Extraction

A real-time global intelligence platform that ingests, normalizes, extracts, and indexes high-quality global news and official publications.

---

## 1. Project Purpose

The long-term vision of the **Global Intelligence Platform** is to convert raw worldwide information into structured events and entities, cluster related reports, construct an evidence-backed knowledge graph, evaluate economic/market impacts, and present intelligence through interactive dashboards and maps.

- **V0.1 (Data Foundation)**: Ingestion from external sources (RSS, Atom, REST APIs), text cleaning, SHA-256 deduplication, and PostgreSQL persistence.
- **V0.2 (Intelligence Extraction - Active)**:
  - Canonical entity extraction across 18 taxonomy categories.
  - Entity normalization and synonym resolution (countries, central banks, commodities, currencies).
  - Document-entity association tracking with roles and extraction confidence.
  - Granular event metadata extraction with explicit separation between **confidence** and **importance**.
  - Provenance tracking (extractor name, version, and execution timestamp).
  - Processing state machine (`NORMALIZED` -> `EXTRACTION_PENDING` -> `EXTRACTED` / `EXTRACTION_FAILED`).
  - Safe, auditable document reprocessing.
  - REST endpoints for entities, events, and document intelligence.

---

## 2. Architecture

The system is designed as a **Modular Monolith** with clean domain separation:

- **Collectors (`backend/app/collectors`)**: Network retrieval and raw vendor parsing (RSS, Atom, REST).
- **Processors (`backend/app/processors`)**: Text sanitization, HTML stripping, UTC date enforcement, SHA-256 hashing.
- **Extractors (`backend/app/extractors`)**:
  - `BaseIntelligenceExtractor`: Core extractor abstraction.
  - `RuleBasedIntelligenceExtractor`: High-reliability deterministic entity and event trigger extractor (zero external API keys needed).
  - `EntityNormalizer`: Curated entity canonicalization engine and alias dictionary.
- **Services (`backend/app/services`)**: Ingestion, entity management, event querying, and transactional extraction pipeline with atomic rollback and reprocessing.
- **API (`backend/app/api`)**: FastAPI v1 endpoints for health, sources, documents, entities, and events.
- **Database (`backend/app/models`, `backend/alembic`)**: SQLAlchemy 2.0 models with Alembic schema versioning for PostgreSQL 16.

For full architectural details, see:
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/v0_2_intelligence_extraction.md`](docs/v0_2_intelligence_extraction.md)

---

## 3. Technology Stack

- **Runtime**: Python 3.11+
- **API Framework**: FastAPI 0.110+ with Uvicorn
- **Validation**: Pydantic v2 & Pydantic-Settings
- **ORM & Database**: SQLAlchemy 2.0, PostgreSQL 16 (`psycopg3`), SQLite (test fallback)
- **Migrations**: Alembic 1.13+
- **HTTP Client**: HTTPX with Tenacity
- **Feed Parsing**: Feedparser 6.0+
- **Testing**: Pytest, Pytest-Asyncio, Pytest-Cov

---

## 4. API Specification

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Root system health and database connectivity |
| `GET` | `/api/v1/health` | API v1 health probe |
| `GET` | `/api/v1/sources` | List configured intelligence sources |
| `POST` | `/api/v1/sources` | Register a new source |
| `GET` | `/api/v1/sources/{id}` | Retrieve specific source details |
| `POST` | `/api/v1/sources/{id}/ingest` | Trigger source ingestion |
| `GET` | `/api/v1/documents` | Paginated documents listing |
| `GET` | `/api/v1/documents/{id}` | Get document by UUID |
| `GET` | `/api/v1/documents/{id}/entities` | List entity mentions for a document |
| `GET` | `/api/v1/documents/{id}/events` | List events extracted from a document |
| `POST` | `/api/v1/documents/{id}/extract` | Trigger document intelligence extraction (`reprocess=true/false`) |
| `GET` | `/api/v1/entities` | Paginated listing of canonical entities |
| `GET` | `/api/v1/entities/{id}` | Retrieve single canonical entity by UUID |
| `GET` | `/api/v1/events` | Paginated listing of extracted events |
| `GET` | `/api/v1/events/{id}` | Retrieve single extracted event by UUID |

---

## 5. Quick Start

### 1. Start PostgreSQL 16
```powershell
.\.venv\Scripts\python.exe scripts/start_postgres.py
```

### 2. Apply Alembic Migrations
```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

### 3. Run FastAPI Application
```powershell
.\.venv\Scripts\uvicorn.exe backend.app.main:app --reload --port 8000
```
Interactive OpenAPI documentation will be available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

---

## 6. Running Tests & Verification

### Run Full Test Suite (78 Tests, 91% Coverage):
```powershell
.\.venv\Scripts\pytest.exe -v
```

### Run PostgreSQL 16 End-to-End Verification:
```powershell
.\.venv\Scripts\python.exe scripts/verify_v0_2_e2e.py
```

---

## 7. Current V0.2 Limitations

- **No Cross-Source Event Clustering**: Events are extracted per-document; multi-document event grouping is reserved for V0.3.
- **Bounded Importance Heuristic**: Event importance is derived from keyword triggers, headline prominence, and category baselines, not a predictive econometric model.
- **No Background Task Queue**: Extraction is executed synchronously via API or pipeline services; worker queues belong to V0.8.
- **No Knowledge Graph Visualization**: Visual graphs and 3D globes are planned for later versions.

---

## 8. Roadmap

- **V0.1** — Data Foundation *(Completed)*
- **V0.2** — Intelligence Extraction *(Completed)*
- **V0.3** — Deduplication & Event Clustering *(Next)*
- **V0.4** — Global Intelligence Dashboard
- **V0.5** — Economic Intelligence
- **V0.6** — Market Intelligence
- **V0.7** — Impact & Relationship Engine
- **V0.8** — Real-Time Intelligence & Queues
- **V0.9** — Interactive Globe
- **V1.0** — Integrated Global Intelligence Platform
