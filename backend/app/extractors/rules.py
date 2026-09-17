import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from backend.app.extractors.base import BaseIntelligenceExtractor
from backend.app.extractors.normalizer import (
    EntityNormalizer,
    _ENTITY_KNOWLEDGE_BASE,
    _REGISTERED_CATALOG,
    NormalizedEntityResult,
    disambiguate_georgia_context,
)
from backend.app.schemas.extraction import (
    ExtractionResult,
    ExtractedEntityMention,
    ExtractedEventItem,
    ExtractionProvenance,
    EntityType,
    EntityRole,
    EventType,
)
from backend.app.utils.time import utc_now
from backend.app.extractors.economic import DeterministicEconomicExtractor


# Curated Event Trigger Rules: (EventType, [trigger phrases], base_importance, base_confidence)
_EVENT_TRIGGER_RULES: List[Tuple[EventType, List[str], float, float]] = [
    (
        EventType.CENTRAL_BANK_DECISION,
        [
            "rate hike", "rate cut", "hikes rates", "cuts rates", "holds rates",
            "raise rates", "raises rates", "interest rate decision", "monetary policy decision",
            "benchmark interest rate", "benchmark interest rates", "leaves interest rates unchanged",
            "raises interest rates", "lowers interest rates", "fed decision", "ecb decision",
            "liquidity facility", "swap lines", "holds benchmark rates", "benchmark rates",
            "benchmark rate", "rates steady", "rate decision", "increases key benchmark rate",
            "increases benchmark rate", "increases benchmark rates", "raises benchmark rates",
            "raises benchmark interest rates",
        ],
        0.88,
        0.92,
    ),
    (
        EventType.CONFLICT,
        [
            "missile attack", "airstrike", "air strike", "artillery fire", "drone strike",
            "rocket attack", "military invasion", "invaded", "clashes erupt",
            "combat operations", "casualties reported", "shelling", "military offensive",
            "attack", "attacks", "escalates attacks", "military advance", "military strikes", "air strikes",
        ],
        0.95,
        0.88,
    ),
    (
        EventType.TRADE_ACTION,
        [
            "tariff", "tariffs", "trade agreement", "trade pact", "trade deal",
            "trade corridor", "trade barriers", "export restrictions", "export controls",
            "import restrictions", "customs duties",
        ],
        0.82,
        0.89,
    ),
    (
        EventType.SANCTION,
        [
            "sanctions", "sanctioned", "asset freeze", "asset freezes",
            "blacklisted", "trade embargo", "economic penalties", "penalties imposed",
        ],
        0.85,
        0.90,
    ),
    (
        EventType.MILITARY_ACTION,
        [
            "military drill", "military exercise", "troop deployment", "troops deployed",
            "naval exercise", "air defense interception", "warships deployed", "carrier strike group",
        ],
        0.75,
        0.85,
    ),
    (
        EventType.ELECTION,
        [
            "presidential election", "parliamentary election", "general election",
            "polls open", "vote counting", "landslide victory", "ballot count", "election results",
        ],
        0.82,
        0.92,
    ),
    (
        EventType.POLITICAL_CHANGE,
        [
            "prime minister resigns", "president resigns", "cabinet reshuffle",
            "parliament dissolved", "coup d'etat", "coup attempt", "impeachment",
            "no-confidence vote", "motion of censure",
        ],
        0.90,
        0.88,
    ),
    (
        EventType.COMMODITY_EVENT,
        [
            "oil production cut", "opec quota", "crude output", "pipeline shutdown",
            "gas supply halted", "grain deal", "grain shipment", "oil reserves released",
            "production quota", "production quotas", "target quotas", "output limits",
            "production cut quotas",
        ],
        0.80,
        0.87,
    ),
    (
        EventType.ECONOMIC_RELEASE,
        [
            "inflation rose", "inflation fell", "inflation hits", "cpi rose", "cpi dropped",
            "gdp growth", "gdp contracted", "unemployment rate", "jobs report",
            "retail sales", "economic outlook", "consumer price index rose",
            "inflation increase", "inflation rises", "inflation jumped", "inflation accelerates",
        ],
        0.78,
        0.88,
    ),
    (
        EventType.INTERNATIONAL_AGREEMENT,
        [
            "signed agreement", "signs accord", "peace accord", "bilateral treaty",
            "strategic partnership", "mou signed", "joint declaration", "landmark accord",
            "energy accord", "reached consensus", "consensus reached", "agrees on",
            "sign trilateral", "signs maritime fishing accord", "finalize lng supply agreement",
            "supply agreement", "fishing accord",
        ],
        0.85,
        0.90,
    ),
    (
        EventType.GOVERNMENT_DECISION,
        [
            "executive order", "government decree", "parliament passes", "legislation approved",
            "official ban", "regulatory clearance", "cabinet approves", "sanitation ordinance",
            "approves sanitation ordinance",
        ],
        0.70,
        0.83,
    ),
    (
        EventType.NATURAL_DISASTER,
        [
            "magnitude earthquake", "tsunami warning", "category hurricane",
            "wildfire emergency", "flash flooding", "volcanic eruption",
        ],
        0.88,
        0.93,
    ),
    (
        EventType.DISASTER,
        [
            "earthquake", "seismic observation", "magnitude", "tsunami warning", "category hurricane",
            "wildfire emergency", "flash flooding", "volcanic eruption", "natural disaster",
        ],
        0.88,
        0.95,
    ),
    (
        EventType.CORPORATE_ACTION,
        [
            "to acquire", "merger agreement", "chapter 11 bankruptcy",
            "antitrust lawsuit", "quarterly profit", "revenue report",
            "enters agreement to acquire",
        ],
        0.65,
        0.84,
    ),
    (
        EventType.ATTACK,
        [
            "missile attack", "drone strike", "airstrike", "suicide bombing",
            "artillery barrage", "shelling attack", "rocket barrage", "armed ambush",
        ],
        0.95,
        0.90,
    ),
    (
        EventType.DIPLOMATIC_ACTION,
        [
            "expels diplomats", "summons ambassador", "recalls ambassador",
            "severs diplomatic ties", "diplomatic mission", "peace summit", "bilateral talks",
        ],
        0.85,
        0.89,
    ),
    (
        EventType.PROTEST,
        [
            "mass protest", "demonstrators march", "protesters clash", "nationwide strike",
            "rally against", "civil unrest", "crowds demand",
        ],
        0.80,
        0.88,
    ),
    (
        EventType.COUP,
        [
            "military coup", "junta seizes power", "ousts president", "deposed leader",
            "army takes control", "dissolves constitution",
        ],
        0.95,
        0.92,
    ),
    (
        EventType.TARIFF,
        [
            "tariff hike", "imposes tariffs", "tariffs levied", "customs tariff",
            "retaliatory tariffs", "duties imposed", "trade tariff",
        ],
        0.85,
        0.90,
    ),
    (
        EventType.INFRASTRUCTURE_FAILURE,
        [
            "power grid collapse", "blackout hit", "pipeline rupture", "dam failure",
            "bridge collapse", "undersea cable severed", "telecoms outage",
        ],
        0.85,
        0.88,
    ),
    (
        EventType.CYBER_INCIDENT,
        [
            "ransomware attack", "data breach", "cyberattack on", "hacked systems",
            "zero-day exploit", "ddos assault", "espionage malware",
        ],
        0.86,
        0.90,
    ),
    (
        EventType.ENVIRONMENTAL_EVENT,
        [
            "oil spill", "chemical leak", "toxic plume", "nuclear contamination",
            "severe drought", "ecological disaster",
        ],
        0.82,
        0.87,
    ),
    (
        EventType.HUMANITARIAN_EVENT,
        [
            "famine declared", "refugee exodus", "aid convoy blocked", "humanitarian corridor",
            "cholera outbreak", "civilian displacement",
        ],
        0.84,
        0.89,
    ),
    (
        EventType.TRANSPORTATION_EVENT,
        [
            "plane crash", "train derailment", "cargo ship ran aground", "vessel collision",
            "flight grounded", "airspace closed",
        ],
        0.80,
        0.88,
    ),
    (
        EventType.ENERGY_DISRUPTION,
        [
            "gas transit halted", "oil refinery explosion", "lng export terminal outage",
            "grid blackout", "power generation cut",
        ],
        0.88,
        0.91,
    ),
    (
        EventType.SUPPLY_CHAIN_DISRUPTION,
        [
            "shipping chokepoint blocked", "suez canal grounded", "port strike",
            "strait transit suspended", "semiconductor shortage",
        ],
        0.85,
        0.89,
    ),
    (
        EventType.DISASTER,
        [
            "magnitude earthquake", "tsunami warning", "category hurricane",
            "wildfire emergency", "flash flooding", "volcanic eruption",
        ],
        0.88,
        0.93,
    ),
]

# Negation detection patterns (window search)
_NEGATION_PRE_REGEX = re.compile(
    r"\b(?:not|will\s+not|won'?t|did\s+not|didn'?t|does\s+not|doesn'?t|has\s+not|hasn'?t|"
    r"have\s+not|haven'?t|would\s+not|wouldn'?t|could\s+not|couldn'?t|"
    r"denied|denies|denying|ruled\s+out|rules\s+out|ruling\s+out|"
    r"decided\s+not\s+to|decides\s+not\s+to|no\s+plans\s+to|unlikely\s+to|"
    r"rejected|rejects|rejecting|refused\s+to|refuses\s+to|refusing\s+to|"
    r"no\s+intention\s+to|halted\s+plans\s+to|dismissed|dismisses|dismissing|"
    r"failed\s+to|never|neither|nor|without|refutes|opposes?)\b",
    re.IGNORECASE,
)

_NEGATION_POST_REGEX = re.compile(
    r"\b(?:was|were|is|are|been)\s+(?:ruled\s+out|rejected|denied|dismissed|unlikely)\b",
    re.IGNORECASE,
)

# Retrospective / Historical analysis markers
_RETROSPECTIVE_MARKERS = re.compile(
    r"\b(?:reflections\s+on|anniversary\s+of|remembering|retrospective|"
    r"decades\s+ago|\d+\s+years\s+ago|thirty-six\s+years\s+ago|twenty\s+years\s+ago|"
    r"during\s+the\s+19\d\ds?|in\s+the\s+19\d\ds?|looking\s+back\s+on|revisiting|"
    r"historical\s+retrospective|history\s+of|historians?\s+review|historians?\s+examine|"
    r"lessons\s+from\s+the|commemorates?|commemorating)\b",
    re.IGNORECASE,
)

_HISTORICAL_EVENT_PHRASE = re.compile(
    r"\b(19\d{2}|200\d|201\d)\s+(?:Gulf\s+War|Financial\s+Crisis|War|Invasion|Crash|Depression|Crisis)\b",
    re.IGNORECASE,
)

# Locative prepositions for event location attachment
_LOCATIVE_PREPOSITIONS = re.compile(
    r"\b(?i:in|near|at|across|over|outside|off\s+the\s+coast\s+of|along|into)\s+(?:the\s+)?([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})",
)


class RuleBasedIntelligenceExtractor(BaseIntelligenceExtractor):
    """Deterministic, high-reliability intelligence extractor (V0.2.1 Hardened).
    
    Extracts structured entity mentions and event metadata using curated regex dictionaries,
    local window-based negation detection, temporal retrospective filtering, prepositional
    location disambiguation, and contextual entity role assignment.
    """

    def __init__(self, version: str = "0.2.1"):
        super().__init__(name="RuleBasedIntelligenceExtractor", version=version)
        self._entity_patterns: List[Tuple[NormalizedEntityResult, str, re.Pattern]] = []
        self._trigger_patterns: List[Tuple[EventType, List[Tuple[str, re.Pattern]], float, float]] = []
        self._economic_extractor = DeterministicEconomicExtractor()
        self._build_patterns()
        self._build_trigger_patterns()

    def _build_patterns(self) -> None:
        """Compile high-precision regex patterns for catalog entities with strict word boundaries."""
        seen_patterns = set()
        compiled_list = []

        for entity, surface_forms in _REGISTERED_CATALOG:
            for surface in surface_forms:
                clean_surface = surface.strip()
                if len(clean_surface) < 2:
                    continue

                # For short 2-3 char uppercase acronyms (US, UK, UN, EU, LNG, USD, EUR, CPI, GDP, etc.), enforce case-sensitive match
                if len(clean_surface) <= 3 and clean_surface.isupper():
                    pattern_str = r"\b" + re.escape(clean_surface) + r"\b"
                    flags = 0
                else:
                    pattern_str = r"\b" + re.escape(clean_surface) + r"\b"
                    flags = re.IGNORECASE

                cache_key = (clean_surface, flags)
                if cache_key not in seen_patterns:
                    seen_patterns.add(cache_key)
                    try:
                        compiled = re.compile(pattern_str, flags)
                        compiled_list.append((entity, clean_surface, compiled, len(clean_surface)))
                    except re.error:
                        continue

        # Sort patterns by surface length descending so longer phrases match first
        compiled_list.sort(key=lambda x: x[3], reverse=True)
        self._entity_patterns = [(e, s, p) for e, s, p, _ in compiled_list]

    def _build_trigger_patterns(self) -> None:
        """Compile regex word boundary patterns for all event triggers."""
        self._trigger_patterns = []
        for event_type, triggers, base_imp, base_conf in _EVENT_TRIGGER_RULES:
            compiled_triggers = []
            for t in triggers:
                try:
                    p = re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE)
                    compiled_triggers.append((t, p))
                except re.error:
                    continue
            self._trigger_patterns.append((event_type, compiled_triggers, base_imp, base_conf))

    def extract(
        self,
        document_id: UUID,
        title: str,
        description: Optional[str] = None,
        content: Optional[str] = None,
        published_at: Optional[datetime] = None,
    ) -> ExtractionResult:
        full_text = f"{title}\n{description or ''}\n{content or ''}".strip()

        extracted_entities: List[ExtractedEntityMention] = []
        entity_id_map: Dict[str, ExtractedEntityMention] = {}

        # -------------------------------------------------------------
        # 1. Entity Extraction with Strict Boundaries & Contextual Roles
        # -------------------------------------------------------------
        for entity, alias_surface, pattern in self._entity_patterns:
            match = pattern.search(full_text)
            if not match:
                continue

            mention_text = match.group(0)
            canonical = entity.canonical_name
            norm_key = entity.normalized_name

            # Disambiguate Georgia if applicable
            current_entity_type = entity.entity_type
            current_country_code = entity.country_code
            current_desc = entity.description
            if canonical == "Georgia":
                current_entity_type, current_country_code, current_desc = disambiguate_georgia_context(full_text)

            # Avoid duplicates within same document
            if norm_key in entity_id_map:
                continue

            in_title = bool(pattern.search(title))

            # Role assignment via contextual heuristics
            role = self._determine_contextual_role(
                entity=entity,
                mention_text=mention_text,
                full_text=full_text,
                title=title,
                in_title=in_title,
            )

            # Confidence score calculation
            if in_title:
                confidence = 0.95
            elif len(alias_surface) > 3:
                confidence = 0.90
            else:
                confidence = 0.85

            mention_record = ExtractedEntityMention(
                entity_type=current_entity_type,
                canonical_name=canonical,
                normalized_name=norm_key,
                mention_text=mention_text,
                role=role,
                confidence=confidence,
                country_code=current_country_code,
                description=current_desc,
                metadata={
                    "in_title": in_title,
                    "matched_alias": alias_surface,
                },
            )
            extracted_entities.append(mention_record)
            entity_id_map[norm_key] = mention_record

        # -------------------------------------------------------------
        # 2. Event Extraction with Negation, Retrospective & Location Hardening
        # -------------------------------------------------------------
        extracted_events: List[ExtractedEventItem] = []

        for event_type, compiled_triggers, base_importance, base_confidence in self._trigger_patterns:
            # Find all matching trigger instances
            matched_instances = []
            for t_text, t_pattern in compiled_triggers:
                for match in t_pattern.finditer(full_text):
                    matched_instances.append((t_text, match.start(), match.end()))

            if not matched_instances:
                continue

            # Check if all instances of this trigger in the document are negated
            valid_instances = []
            for t_text, start_idx, end_idx in matched_instances:
                if not self._is_negated_trigger(full_text, start_idx, end_idx):
                    valid_instances.append((t_text, start_idx, end_idx))

            # If all occurrences are negated, emit NO positive event
            if not valid_instances:
                continue

            # Pick the longest / most specific valid trigger, prioritizing title triggers
            best_trigger, best_start, best_end = max(
                valid_instances,
                key=lambda x: (x[0].lower() in title.lower(), len(x[0]))
            )
            in_title = best_trigger.lower() in title.lower()

            # Check historical / retrospective filtering
            if self._is_historical_context(title=title, full_text=full_text, event_type=event_type):
                # Suppress current event generation on retrospective analyses
                continue

            # Extract sentence containing the trigger for context and location linkage
            trigger_sentence = self._extract_trigger_sentence(full_text, best_trigger) or title

            # Disambiguate event location using prepositional locative parsing and event taxonomy
            loc_entity_name = self._disambiguate_event_location(
                trigger_sentence=trigger_sentence,
                full_text=full_text,
                extracted_entities=extracted_entities,
                event_type=event_type,
                trigger_word=best_trigger,
            )

            # Importance calculation
            importance = min(1.0, round(base_importance + (0.05 if in_title else 0.0), 2))

            # Confidence calculation calibrated against semantic evidence
            confidence = base_confidence
            if in_title:
                confidence += 0.05
            if loc_entity_name:
                confidence += 0.05
            else:
                confidence -= 0.05
            if len(valid_instances) > 1:
                confidence += 0.03
            confidence = max(0.50, min(0.98, round(confidence, 2)))

            # Event title & summary
            event_title = f"{title} [{best_trigger.title()}]" if not in_title else title
            summary = trigger_sentence or description or title

            extracted_events.append(
                ExtractedEventItem(
                    event_type=event_type.value,
                    title=event_title,
                    summary=summary,
                    event_time=published_at,
                    location_entity_name=loc_entity_name,
                    confidence=confidence,
                    importance=importance,
                    metadata={
                        "trigger_word": best_trigger,
                        "start_char": best_start,
                        "end_char": best_end,
                        "matched_triggers_count": len(valid_instances),
                        "in_title": in_title,
                        "location_disambiguated": bool(loc_entity_name),
                        "trigger_sentence": trigger_sentence,
                    },
                )
            )

        # Extract structured economic intelligence observations
        economic_observations = self._economic_extractor.extract_economic_intelligence(
            full_text, published_at=published_at
        )

        provenance = ExtractionProvenance(
            extractor_name=self.name,
            extractor_version=self.version,
            processed_at=utc_now(),
            config={"knowledge_base_size": len(_ENTITY_KNOWLEDGE_BASE)},
        )

        return ExtractionResult(
            entities=extracted_entities,
            events=extracted_events,
            economic_observations=economic_observations,
            metadata=provenance,
        )

    def _is_negated_trigger(self, full_text: str, start_idx: int, end_idx: int) -> bool:
        """Examine local clause window around trigger for negation markers."""
        # Preceding window: up to 100 characters before trigger, delimited by clause/sentence boundary
        lookback_limit = max(0, start_idx - 100)
        preceding_text = full_text[lookback_limit:start_idx]

        # Find nearest clause/sentence boundary
        delimiters = [".", "\n", ";", "?", "!", ",", "—", "but ", "however ", "although ", "while "]
        latest_delim_idx = -1
        for d in delimiters:
            idx = preceding_text.rfind(d)
            if idx > latest_delim_idx:
                latest_delim_idx = idx

        if latest_delim_idx != -1:
            pre_window = preceding_text[latest_delim_idx:]
        else:
            pre_window = preceding_text

        if _NEGATION_PRE_REGEX.search(pre_window):
            return True

        # Following window: up to 50 characters for passive negation
        following_text = full_text[end_idx:min(len(full_text), end_idx + 50)]
        if _NEGATION_POST_REGEX.search(following_text):
            return True

        return False

    def _is_historical_context(self, title: str, full_text: str, event_type: EventType) -> bool:
        """Detect whether article describes a historical retrospective rather than a current event."""
        lead_sample = full_text[:400]

        # Check explicit retrospective markers
        has_retrospective_marker = bool(
            _RETROSPECTIVE_MARKERS.search(title) or _RETROSPECTIVE_MARKERS.search(lead_sample)
        )

        # Check explicit past year tokens (before 2024)
        has_past_year = bool(re.search(r"\b(19\d{2}|200\d|201\d|202[0-3])\b", title) or
                            re.search(r"\b(19\d{2}|200\d|201\d|202[0-3])\b", lead_sample))

        # Check compound historical phrases (e.g. '1990 Gulf War', '2008 financial crisis')
        if _HISTORICAL_EVENT_PHRASE.search(title) or _HISTORICAL_EVENT_PHRASE.search(lead_sample):
            return True

        if has_retrospective_marker and has_past_year:
            return True

        if _RETROSPECTIVE_MARKERS.search(title):
            return True

        return False

    def _disambiguate_event_location(
        self,
        trigger_sentence: str,
        full_text: str,
        extracted_entities: List[ExtractedEntityMention],
        event_type: Optional[EventType] = None,
        trigger_word: Optional[str] = None,
    ) -> Optional[str]:
        """Disambiguate event location using prepositional phrases, event taxonomy, and entity roles."""
        geo_entities = [
            e for e in extracted_entities
            if e.entity_type in (EntityType.COUNTRY.value, EntityType.CITY.value, EntityType.LOCATION.value)
        ]
        if not geo_entities:
            return None

        # Rule A: For sovereign national/political events (POLITICAL_CHANGE, ELECTION, GOVERNMENT_DECISION, CENTRAL_BANK_DECISION)
        # Prioritize the sovereign COUNTRY entity over municipal capital city (e.g. France over Paris, Georgia over Tbilisi)
        if event_type in (EventType.POLITICAL_CHANGE, EventType.ELECTION, EventType.GOVERNMENT_DECISION, EventType.CENTRAL_BANK_DECISION):
            country_geos = [geo for geo in geo_entities if geo.entity_type == EntityType.COUNTRY.value]
            if country_geos:
                return country_geos[0].canonical_name

        # Rule B: Check in trigger_sentence for locative preposition phrases with distance scoring
        prep_candidates = []
        trigger_pos = trigger_sentence.lower().find(trigger_word.lower()) if trigger_word else 0

        for match in _LOCATIVE_PREPOSITIONS.finditer(trigger_sentence):
            match_start = match.start()
            is_attribution = bool(re.search(r"\b(?:officials|ministers|policymakers|delegates|leaders|diplomats)\s*$", trigger_sentence[:match_start], re.IGNORECASE))
            prep_target = match.group(1).strip().lower()
            for geo_ent in geo_entities:
                if (geo_ent.canonical_name.lower() in prep_target or
                    geo_ent.mention_text.lower() in prep_target):
                    dist = abs(match_start - trigger_pos) + (1000 if is_attribution else 0)
                    prep_candidates.append((dist, geo_ent.canonical_name))

        if prep_candidates:
            prep_candidates.sort(key=lambda x: x[0])
            return prep_candidates[0][1]

        # Rule C: Check full text for prepositional phrases (e.g. 'Ministers met in Berlin...')
        for match in _LOCATIVE_PREPOSITIONS.finditer(full_text):
            prep_target = match.group(1).strip().lower()
            for geo_ent in geo_entities:
                if (geo_ent.canonical_name.lower() in prep_target or
                    geo_ent.mention_text.lower() in prep_target):
                    return geo_ent.canonical_name

        # Rule D: In trigger sentence, prioritize non-actor geographic entities over actor entities
        non_actor_geos = [
            geo for geo in geo_entities
            if geo.role != EntityRole.ACTOR.value and (
                geo.canonical_name.lower() in trigger_sentence.lower() or
                geo.mention_text.lower() in trigger_sentence.lower()
            )
        ]
        if non_actor_geos:
            return non_actor_geos[0].canonical_name

        # Rule E: Any geographic entity with role == LOCATION in document
        location_role_geos = [geo for geo in geo_entities if geo.role == EntityRole.LOCATION.value]
        if location_role_geos:
            return location_role_geos[0].canonical_name

        # Fallback to first non-actor or first geo
        non_actors = [geo for geo in geo_entities if geo.role != EntityRole.ACTOR.value]
        if non_actors:
            return non_actors[0].canonical_name

        return geo_entities[0].canonical_name

    def _determine_contextual_role(
        self,
        entity: NormalizedEntityResult,
        mention_text: str,
        full_text: str,
        title: str,
        in_title: bool,
    ) -> str:
        """Assign contextual role based on syntactic context, prepositions, and action verbs."""
        etype = entity.entity_type

        # 1. Non-geographic fixed taxonomies
        if etype == EntityType.COMMODITY.value:
            return EntityRole.COMMODITY.value
        if etype in (EntityType.CURRENCY.value, EntityType.CRYPTOCURRENCY.value):
            return EntityRole.CURRENCY.value
        if etype == EntityType.ECONOMIC_INDICATOR.value:
            return EntityRole.INDICATOR.value
        if etype in (EntityType.CENTRAL_BANK.value, EntityType.INTERNATIONAL_ORGANIZATION.value, EntityType.GOVERNMENT.value):
            if re.search(r"\b(?:in\s+audience|attended\s+by|spectator)\b", full_text, re.IGNORECASE):
                return EntityRole.OTHER.value
            return EntityRole.ACTOR.value

        # 2. Companies
        if etype == EntityType.COMPANY.value:
            if re.search(r"\b(?:in\s+audience|representative\s+in\s+audience|delegate\s+listened|spectator|attended\s+by)\b", full_text, re.IGNORECASE):
                return EntityRole.OTHER.value
            if re.search(r"\b(?:acquires?|merges?|reports?|enters\s+agreement|announced)\b", full_text, re.IGNORECASE):
                return EntityRole.ACTOR.value
            return EntityRole.COMPANY.value

        # 3. Countries, Cities, and Locations
        if etype in (EntityType.COUNTRY.value, EntityType.CITY.value, EntityType.LOCATION.value):
            # Check passive/biographical background context (Doc #19 memoirs, heritage)
            background_regex = re.compile(
                r"\b(?:born\s+in|educated\s+in|memoirs\s+from|cottage\s+in|hiking\s+in|"
                r"growing\s+up\s+in|visiting\s+relatives\s+in|childhood\s+in|vacation\s+in|"
                r"archives\s+regarding|art\s+heritage\s+in)\s+" + re.escape(mention_text) + r"\b",
                re.IGNORECASE,
            )
            if background_regex.search(full_text):
                return EntityRole.OTHER.value

            # Locative preposition takes strict priority: 'in Ukraine', 'at Paris', 'across Georgia', 'in Tokyo'
            locative_regex = re.compile(
                r"\b(?:in|at|near|across|over|outside|off\s+the\s+coast\s+of|along|into)\s+" + re.escape(mention_text) + r"\b",
                re.IGNORECASE,
            )
            if locative_regex.search(full_text):
                # Exception: Conjoined subject in title before action verb: 'Germany, France, and Italy Sign...'
                if in_title and re.search(r"\b(?:signs?|signed|issues?|issued|condemns?|condemned|ratifies?|ratified|agrees?)\b", title, re.IGNORECASE):
                    if not locative_regex.search(title):
                        return EntityRole.ACTOR.value
                return EntityRole.LOCATION.value

            # Check sovereign actor context (action verbs following subject)
            actor_action_regex = re.compile(
                r"\b" + re.escape(mention_text) + r"(?:,\s+[A-Z][a-zA-Z\s]+)*\s*(?:and\s+[A-Z][a-zA-Z\s]+)?\s+"
                r"\b(?:signs?|signed|ratifies?|ratified|issues?|issued|condemns?|condemned|"
                r"approves?|approved|announces?|announced|agrees?|agreed|deploys?|deployed|"
                r"formalizes?|formalized|supports?|supported|sanctions?|sanctioned|launches?|"
                r"mobilizes?|mobilized|enacts?|enacted|votes?|voted|passes?|passed|confirmed|confirms|"
                r"released?|releasing|declared?|declaring|urged?|urging|challenged)\b",
                re.IGNORECASE,
            )
            if actor_action_regex.search(full_text) or actor_action_regex.search(title):
                return EntityRole.ACTOR.value

            # Default heuristic for geographic entities
            if in_title and not locative_regex.search(title) and etype == EntityType.COUNTRY.value:
                return EntityRole.ACTOR.value
            return EntityRole.LOCATION.value


        return EntityRole.OTHER.value

    def _extract_trigger_sentence(self, text: str, trigger: str) -> Optional[str]:
        """Extract the sentence containing the trigger for context summary."""
        sentences = re.split(r"[.\n]", text)
        for s in sentences:
            if trigger.lower() in s.lower():
                cleaned = s.strip()
                if len(cleaned) > 15:
                    return cleaned[:300]
        return None

