# Global Intelligence Platform — Architecture Design (V0.1 + V0.2)

## 1. Architectural Overview

The **Global Intelligence Platform** captures, normalizes, extracts, and analyzes global information at scale.
- **V0.1** establishes the foundational data ingestion and normalization tier.
- **V0.2** establishes the intelligence extraction layer (canonical entities, document-entity associations, and extracted event metadata).

```mermaid
flowchart TD
    subgraph External Sources
        RSS[RSS / Atom Feeds]
        API[Structured JSON APIs]
        Official[Official Government / UN Releases]
    end

    subgraph Data Ingestion Tier (V0.1)
        RC[RSSCollector]
        AC[APICollector]
        Registry[Collector Registry & Factory]
    end

    subgraph Processing & Normalization (V0.1)
        Norm[Normalizer]
        Hash[Content Hasher SHA-256]
        Schema[NormalizedDocument Model]
    end

    subgraph Persistence Tier
        IngestService[Ingestion Service]
        Dedupe[Deduplication Engine]
        DB[(PostgreSQL Database)]
        Alembic[Alembic Migrations]
    end

    subgraph Intelligence Extraction Tier (V0.2)
        ExtractService[Extraction Service]
        RuleExtractor[RuleBasedIntelligenceExtractor]
        EntityNorm[Entity Normalization & Taxonomy]
    end

    subgraph API Presentation Tier
        FastAPI[FastAPI Gateway]
        Health[GET /health]
        SourcesAPI[Sources API]
        DocsAPI[Documents API]
        EntitiesAPI[Entities API]
        EventsAPI[Events API]
    end

    RSS --> RC
    API --> AC
    Official --> RC
    RC --> Registry
    AC --> Registry
    Registry --> Norm
    Norm --> Hash
    Hash --> Schema
    Schema --> IngestService
    IngestService --> Dedupe
    Dedupe --> DB
    Alembic -.-> DB

    DB --> ExtractService
    ExtractService --> RuleExtractor
    RuleExtractor --> EntityNorm
    EntityNorm --> DB

    DB --> FastAPI
    FastAPI --> Health
    FastAPI --> SourcesAPI
    FastAPI --> DocsAPI
    FastAPI --> EntitiesAPI
    FastAPI --> EventsAPI
```

---

## 2. Core Design Principles

1. **Separation of Concerns**:
   - Ingestion collectors parse and normalize source payloads.
   - Normalizers clean text and enforce strict UTC timestamps.
   - Intelligence extractors parse mentions and events without modifying raw document content.
   - Persistence services manage ACID database transactions and deduplication.

2. **Immutable Provenance Preservation**:
   - The database retains complete raw payloads in `documents.raw_metadata`.
   - Every extracted entity and event links directly to its source document ID and carries extractor name, version, and execution timestamp.

3. **Timezone Uniformity (Strict UTC)**:
   - All models utilize `UTCDateTime` TypeDecorators and timezone-aware objects (`datetime.now(timezone.utc)`).

4. **Deterministic Deduplication & Canonicalization**:
   - Documents deduplicate on `(source_id, content_hash)`.
   - Entities canonicalize via `(entity_type, normalized_name)` unique constraints.

5. **Safe Reprocessing**:
   - Documents can be re-extracted at any time without destroying underlying evidence.
   - Previous run metadata is preserved in `document.raw_metadata["extraction_history"]`.

---

## 3. Database Design

### `sources` Table
- `id` (UUID, Primary Key)
- `name` (VARCHAR(128), Unique, Indexed)
- `source_type` (VARCHAR(32), Indexed)
- `base_url` (VARCHAR(512)), `feed_url` (VARCHAR(1024))
- `reliability_score` (FLOAT, Default 0.8)
- `active` (BOOLEAN, Indexed, Default True)
- `polling_interval_seconds` (INTEGER, Default 300)
- `config_metadata` (JSON, Default `{}`)
- `created_at`, `updated_at` (TIMESTAMPTZ, UTC)

### `documents` Table
- `id` (UUID, Primary Key)
- `source_id` (UUID, Foreign Key `sources.id`, ON DELETE RESTRICT, Indexed)
- `external_id` (VARCHAR(256), Nullable, Indexed)
- `title` (TEXT, Not Null)
- `description` (TEXT, Nullable), `content` (TEXT, Nullable)
- `content_format` (VARCHAR(32), Default `'text/plain'`)
- `url` (TEXT, Indexed)
- `author` (VARCHAR(256), Nullable)
- `published_at` (TIMESTAMPTZ, UTC, Indexed)
- `ingested_at` (TIMESTAMPTZ, UTC)
- `content_hash` (VARCHAR(64), Indexed)
- `language` (VARCHAR(16), Default `'en'`, Indexed)
- `raw_metadata` (JSON, Default `{}`)
- `processing_status` (VARCHAR(32), Indexed) — e.g. `NORMALIZED`, `EXTRACTION_PENDING`, `EXTRACTED`, `EXTRACTION_FAILED`
- `created_at`, `updated_at` (TIMESTAMPTZ, UTC)

### `entities` Table (V0.2)
- `id` (UUID, Primary Key)
- `entity_type` (VARCHAR(64), Indexed, Not Null)
- `canonical_name` (VARCHAR(256), Indexed, Not Null)
- `normalized_name` (VARCHAR(256), Indexed, Not Null)
- `description` (TEXT, Nullable)
- `country_code` (VARCHAR(8), Indexed, Nullable)
- `metadata` (JSON, Default `{}`)
- `created_at`, `updated_at` (TIMESTAMPTZ, UTC)
- *Constraint*: Unique `(entity_type, normalized_name)`

### `document_entities` Table (V0.2)
- `id` (UUID, Primary Key)
- `document_id` (UUID, Foreign Key `documents.id`, ON DELETE CASCADE, Indexed)
- `entity_id` (UUID, Foreign Key `entities.id`, ON DELETE CASCADE, Indexed)
- `mention_text` (VARCHAR(256), Not Null)
- `entity_role` (VARCHAR(64), Indexed, Not Null)
- `confidence` (FLOAT, Not Null)
- `metadata` (JSON, Default `{}`)
- `created_at` (TIMESTAMPTZ, UTC)
- *Constraint*: Unique `(document_id, entity_id, entity_role, mention_text)`

### `extracted_events` Table (V0.2)
- `id` (UUID, Primary Key)
- `document_id` (UUID, Foreign Key `documents.id`, ON DELETE CASCADE, Indexed)
- `event_type` (VARCHAR(64), Indexed, Not Null)
- `event_title` (VARCHAR(512), Not Null)
- `event_summary` (TEXT, Nullable)
- `event_time` (TIMESTAMPTZ, Nullable)
- `location_entity_id` (UUID, Foreign Key `entities.id`, ON DELETE SET NULL, Indexed, Nullable)
- `confidence` (FLOAT, Not Null)
- `importance` (FLOAT, Indexed, Not Null)
- `metadata` (JSON, Default `{}`)
- `created_at`, `updated_at` (TIMESTAMPTZ, UTC)

---

## 4. API Specification

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Root system health and database connectivity |
| `GET` | `/api/v1/health` | API v1 health probe |
| `GET` | `/api/v1/sources` | List configured sources |
| `POST` | `/api/v1/sources` | Register a new source |
| `GET` | `/api/v1/sources/{id}` | Get specific source details |
| `POST` | `/api/v1/sources/{id}/ingest` | Trigger immediate source ingestion |
| `GET` | `/api/v1/documents` | Paginated documents listing |
| `GET` | `/api/v1/documents/{id}` | Get document by UUID |
| `GET` | `/api/v1/documents/{id}/entities` | List entity mentions for a document |
| `GET` | `/api/v1/documents/{id}/events` | List events extracted from a document |
| `POST` | `/api/v1/documents/{id}/extract` | Trigger document intelligence extraction (`reprocess=true/false`) |
| `GET` | `/api/v1/entities` | Paginated listing of canonical entities |
| `GET` | `/api/v1/entities/{id}` | Get single entity by UUID |
| `GET` | `/api/v1/events` | Paginated listing of extracted events |
| `GET` | `/api/v1/events/{id}` | Get single extracted event by UUID |
