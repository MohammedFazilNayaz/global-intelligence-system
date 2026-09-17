# V0.2 — Intelligence Extraction Architecture & Specification

## 1. Executive Summary

**V0.2 (Intelligence Extraction)** extends the V0.1 Data Foundation by transforming unstructured and semi-structured text across ingested documents into structured intelligence.

The pipeline processes documents in a non-destructive, strictly traceable workflow:

```
[SOURCE]
   │
   ▼
[INGEST]
   │
   ▼
[NORMALIZE]
   │
   ▼
[STORE DOCUMENT] (processing_status: "NORMALIZED")
   │
   ▼
[V0.2 INTELLIGENCE EXTRACTION]
   ├── 1. Load & Verify Document
   ├── 2. Extract Mentions & Events (BaseIntelligenceExtractor)
   ├── 3. Normalize & Deduplicate Entities (EntityNormalizer)
   ├── 4. Persist Canonical Entities (`entities` table)
   ├── 5. Persist Document ↔ Entity Links (`document_entities` table)
   ├── 6. Persist Extracted Event Records (`extracted_events` table)
   ├── 7. Record Provenance & Processing Metadata
   └── 8. Transition Document Status (`EXTRACTED` or `EXTRACTION_FAILED`)
```

---

## 2. Entity Taxonomy & Canonicalization

### 2.1 Entity Model (`entities` table)
Each record represents a unique, canonical real-world entity:
- `id` (UUID, Primary Key)
- `entity_type` (VARCHAR(64), Indexed, Not Null)
- `canonical_name` (VARCHAR(256), Indexed, Not Null) — Authoritative display name (e.g., `"United States"`, `"Federal Reserve"`)
- `normalized_name` (VARCHAR(256), Indexed, Not Null) — Stripped, punctuation-free search key (e.g., `"united states"`, `"federal reserve"`)
- `description` (TEXT, Nullable)
- `country_code` (VARCHAR(8), Indexed, Nullable) — ISO 3166-1 alpha-2/alpha-3 (e.g., `"US"`, `"GB"`, `"CN"`)
- `metadata` (JSON, Default `{}`) — Synonyms, alternate aliases, external identifiers
- `created_at`, `updated_at` (TIMESTAMPTZ, UTC)

**Constraint**: `UniqueConstraint("entity_type", "normalized_name")` guarantees no duplicate canonical entities of the same type exist in the database.

### 2.2 Supported Entity Types
- `COUNTRY`: Sovereign states (e.g., United States, China, United Kingdom, Japan, Germany, India, Saudi Arabia, Russia)
- `CITY`: Major administrative capitals and global financial centers (e.g., Washington, D.C., Beijing, London, Tokyo, Brussels)
- `LOCATION`: Strategic geopolitical and geographic areas (e.g., Red Sea, Strait of Hormuz, Taiwan Strait, Gaza Strip)
- `PERSON`: World leaders, policymakers, central bankers, executives (e.g., Jerome Powell, Christine Lagarde)
- `ORGANIZATION`: Generic institutions, agencies, alliances
- `COMPANY`: Multinational corporations, major energy and tech enterprises (e.g., Saudi Aramco, TSMC, Microsoft, Apple, NVIDIA)
- `GOVERNMENT`: Cabinets, administrations, sovereign ministries (e.g., White House, Kremlin, Downing Street, Pentagon)
- `POLITICAL_PARTY`: Major political parties and parliamentary factions
- `CENTRAL_BANK`: Monetary authorities (e.g., Federal Reserve, European Central Bank, Bank of England, Bank of Japan, People's Bank of China)
- `FINANCIAL_INSTITUTION`: Multilateral banks and investment banks (e.g., IMF, World Bank, BIS, Goldman Sachs, JPMorgan Chase)
- `COMMODITY`: Strategic raw materials and energy contracts (e.g., Crude Oil, Brent Crude, Natural Gas, Gold, Silver, Copper, Uranium, Wheat)
- `CURRENCY`: Sovereign fiat foreign exchange assets (e.g., US Dollar, Euro, British Pound, Japanese Yen, Chinese Yuan, Swiss Franc)
- `CRYPTOCURRENCY`: Digital assets and settlement tokens (e.g., Bitcoin, Ethereum)
- `FINANCIAL_ASSET`: Sovereign bonds, treasury bills, debt instruments
- `INDEX`: Benchmark financial indices (e.g., S&P 500, FTSE 100, Nikkei 225)
- `INDUSTRY`: Economic sectors (e.g., semiconductors, defense, maritime shipping)
- `ECONOMIC_INDICATOR`: Macroeconomic metrics (e.g., Consumer Price Index, Gross Domestic Product, Unemployment Rate, Interest Rates, PMI)
- `INTERNATIONAL_ORGANIZATION`: Multilateral bodies (e.g., United Nations, NATO, European Union, OPEC, WHO, WTO, G7, G20)
- `OTHER`: Extensible catch-all category

### 2.3 Entity Normalization Rules
`EntityNormalizer` handles alias canonicalization:
- Punctuation stripping: Dots and apostrophes are cleanly removed without extra spaces (`"U.S.A."` -> `"usa"`, `"People's"` -> `"peoples"`).
- Unicode NFKD normalization and case-folding.
- Synonym mapping:
  - `"USA"`, `"U.S."`, `"United States of America"`, `"the United States"`, `"US"` -> Canonical: `"United States"`, Country Code: `"US"`.
  - `"the Fed"`, `"Fed"`, `"US Fed"` -> Canonical: `"Federal Reserve"`, Type: `"CENTRAL_BANK"`.
  - `"ECB"` -> Canonical: `"European Central Bank"`, Country Code: `"EU"`.
  - `"Brent Crude"`, `"WTI"`, `"Oil"`, `"Petroleum"` -> Canonical: `"Crude Oil"`, Type: `"COMMODITY"`.
  - `"USD"`, `"Greenback"` -> Canonical: `"US Dollar"`, Type: `"CURRENCY"`.
  - `"BTC"` -> Canonical: `"Bitcoin"`, Type: `"CRYPTOCURRENCY"`.

---

## 3. Document ↔ Entity Association (`document_entities` table)

Captures occurrences of entities within specific documents:
- `id` (UUID, Primary Key)
- `document_id` (UUID, Foreign Key `documents.id`, `ON DELETE CASCADE`)
- `entity_id` (UUID, Foreign Key `entities.id`, `ON DELETE CASCADE`)
- `mention_text` (VARCHAR(256), Not Null) — Exact string match in source text (e.g., `"the Fed"`, `"USA"`)
- `entity_role` (VARCHAR(64), Indexed, Not Null) — Contextual role
- `confidence` (FLOAT, 0.0 to 1.0, Not Null)
- `metadata` (JSON, Default `{}`) — Extraction provenance, title vs body flag, matched alias
- `created_at` (TIMESTAMPTZ, UTC)

**Roles Supported**:
- `subject`: Entity is the primary subject of the document or headline
- `actor`: Entity actively performed an action (e.g. central bank raising rates, government signing treaty)
- `target`: Entity targeted by an action (e.g. country targeted by sanctions)
- `location`: Geographic setting of the reported event
- `organization`: Mentioned institution or multilateral body
- `person`: Mentioned human actor
- `company`: Mentioned corporate enterprise
- `commodity`: Mentioned physical commodity
- `currency`: Mentioned monetary currency or cryptocurrency
- `asset`: Mentioned financial asset
- `indicator`: Mentioned economic indicator
- `other`: Generic contextual mention

---

## 4. Event Extraction & Taxonomy (`extracted_events` table)

Stores granular event metadata extracted from single documents:
- `id` (UUID, Primary Key)
- `document_id` (UUID, Foreign Key `documents.id`, `ON DELETE CASCADE`)
- `event_type` (VARCHAR(64), Indexed, Not Null)
- `event_title` (VARCHAR(512), Not Null)
- `event_summary` (TEXT, Nullable)
- `event_time` (TIMESTAMPTZ, Nullable) — Event occurrence or document publication time
- `location_entity_id` (UUID, Foreign Key `entities.id`, `ON DELETE SET NULL`, Nullable)
- `confidence` (FLOAT, 0.0 to 1.0, Not Null) — Certainty that the event occurred and was extracted accurately
- `importance` (FLOAT, 0.0 to 1.0, Not Null) — Significance heuristic based on semantic triggers and scope
- `metadata` (JSON, Default `{}`) — Provenance, trigger keywords, context sentence
- `created_at`, `updated_at` (TIMESTAMPTZ, UTC)

### Initial Event Types
1. `central_bank_decision`: Interest rate changes, monetary policy announcements, swap lines
2. `conflict`: Military strikes, missile attacks, armed clashes, casualties
3. `military_action`: Troop deployments, military exercises, air defense operations
4. `election`: Presidential and parliamentary elections, ballot counts, poll results
5. `political_change`: Coups, resignations of heads of state, cabinet reshuffles
6. `government_decision`: Executive orders, parliamentary bills, official decrees
7. `economic_release`: Inflation prints, GDP statistics, employment figures
8. `trade_action`: Tariffs, export controls, trade corridors, customs duties
9. `sanction`: Asset freezes, entity blacklists, economic embargoes
10. `corporate_action`: Mergers, acquisitions, bankruptcies, antitrust lawsuits
11. `commodity_event`: OPEC quotas, production cuts, pipeline shutdowns, grain agreements
12. `natural_disaster`: Earthquakes, tsunamis, hurricanes, wildfires
13. `market_event`: Liquidity crunches, circuit breakers, sharp asset dislocations
14. `regulatory_action`: SEC/regulatory enforcement, compliance investigations
15. `international_agreement`: Treaties, strategic accords, peace pacts, joint declarations
16. `other`: Uncategorized events

---

## 5. Distinction: Confidence vs Importance

`confidence` and `importance` are fundamentally separated:

| Metric | Meaning | Range | Determined By | Example Scenario |
| :--- | :--- | :--- | :--- | :--- |
| **Confidence** | How certain is the extractor that this event occurred and was correctly classified? | `[0.0, 1.0]` | Precision of keyword matches, headline presence, explicit phrasing | A brief single-sentence rumor of a coup has **low confidence** (e.g., 0.50). An official central bank press release has **high confidence** (e.g., 0.95). |
| **Importance** | How globally significant is the event? | `[0.0, 1.0]` | Scope of impact, multilateral actors involved, severity of triggers | A routine quarterly corporate earnings filing has **low importance** (e.g., 0.40). An outbreak of war or an emergency rate cut has **high importance** (e.g., 0.95). |

> [!WARNING]
> **V0.2 Limitation**: In V0.2, importance is an initial bounded heuristic score derived from trigger keywords, headline prominence, and category baselines. It is **not** a complex predictive econometric or geopolitical equilibrium model. Future versions (V0.3+) will build cross-source correlation and impact modeling.

---

## 6. Processing State Machine & Reprocessing

### 6.1 State Machine
```
[RAW] ──► [NORMALIZED] ──► [EXTRACTION_PENDING] ──┬──► [EXTRACTED]
                                                  └──► [EXTRACTION_FAILED]
```

- `NORMALIZED`: Document ingested and normalized by V0.1.
- `EXTRACTION_PENDING`: Extractor has begun processing.
- `EXTRACTED`: Entities and events stored, provenance stamped.
- `EXTRACTION_FAILED`: Extraction failed; failure message recorded in `raw_metadata["extraction_error"]`; document content preserved completely intact.

### 6.2 Reprocessing Service
When calling `POST /api/v1/documents/{id}/extract?reprocess=true`:
1. The previous extraction run is archived into `raw_metadata["extraction_history"]` with timestamps and previous provenance.
2. Prior `document_entities` and `extracted_events` rows for the document are atomically deleted.
3. Canonical entities in `entities` table remain untouched (preventing disruption to other documents).
4. Extraction is rerun using the current extractor version and knowledge base.
5. All updates execute in a single atomic database transaction.

---

## 7. Extractor Abstraction & Replaceability

The architecture decouples extraction from database storage via `BaseIntelligenceExtractor`:

```python
class BaseIntelligenceExtractor(ABC):
    @abstractmethod
    def extract(
        self,
        document_id: UUID,
        title: str,
        description: Optional[str] = None,
        content: Optional[str] = None,
        published_at: Optional[datetime] = None,
    ) -> ExtractionResult: ...
```

- **Default Engine**: `RuleBasedIntelligenceExtractor` (v0.2.0):
  - Deterministic, runs offline, zero external API keys needed, sub-millisecond execution.
  - Curated regex patterns with boundary checking.
- **Factory**: `get_extractor(name=None)` resolves the active extraction implementation dynamically.

---

## 8. REST API Specification

| Method | Endpoint | Query Parameters | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/entities` | `entity_type`, `country_code`, `search`, `page`, `page_size` | Paginated listing of canonical entities |
| `GET` | `/api/v1/entities/{id}` | None | Get single entity details |
| `GET` | `/api/v1/documents/{id}/entities` | None | Get all entity mentions in a document |
| `GET` | `/api/v1/documents/{id}/events` | None | Get all events extracted from a document |
| `GET` | `/api/v1/events` | `event_type`, `document_id`, `min_confidence`, `min_importance`, `order_by`, `page`, `page_size` | Paginated listing of extracted events |
| `GET` | `/api/v1/events/{id}` | None | Get single extracted event |
| `POST` | `/api/v1/documents/{id}/extract` | `reprocess` (bool, default False) | Trigger extraction pipeline for a document |

---

## 9. Migration Path Toward V0.3

V0.2 strictly isolates document-level intelligence extraction. Future versions will build on top of these foundation tables:
- **V0.3 Event Clustering**: Multi-document cross-source event consolidation (clustering `extracted_events` into unified global events).
- **V0.4 Entity Resolution & Graph**: Cross-lingual entity matching and semantic relationship graphs between `entities`.
- **V0.5 Impact & Prediction**: Market sensitivity analysis and trading signal inference.
