import re
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

from backend.app.schemas.relationship import RelationshipType, EntityRelationshipCreate
from backend.app.schemas.extraction import EntityType
from backend.app.extractors.normalizer import _REGISTERED_CATALOG

# Map canonical entity names and all aliases bidirectionally to registered surface aliases
_CANONICAL_ALIASES_MAP: Dict[str, List[str]] = {}
for _res, _aliases in _REGISTERED_CATALOG:
    all_forms = list(_aliases)
    if _res.canonical_name not in all_forms:
        all_forms.append(_res.canonical_name)
    _CANONICAL_ALIASES_MAP[_res.canonical_name] = all_forms
    _CANONICAL_ALIASES_MAP[_res.normalized_name] = all_forms
    for _a in _aliases:
        _CANONICAL_ALIASES_MAP[_a] = all_forms


# Deterministic Relational Predicate Rules
# (RelationshipType, [active regexes], [passive regexes], default_confidence)
_RELATIONSHIP_RULES = [
    (
        RelationshipType.LEADS,
        [
            re.compile(r"\b(?:(?:is|was|serves|served|appointed|elected)\s+(?:as\s+)?(?:the\s+)?)?(?:Chair|Chairman|Chairperson|President|Governor|Director|Chief\s+Executive\s+Officer|CEO|head|leader|Prime\s+Minister|Premier|Chancellor|Foreign\s+Minister|Defence\s+Minister|Secretary\s+of\s+State|Supreme\s+Leader|spokesman|spokesperson|envoy|commander)\s+(?:at|of|for)\b", re.IGNORECASE),
            re.compile(r"\b(?:leads|led|preside(?:s|d)?\s+over(?:\s+[\w\s]+)?\s+(?:at|of)|preside(?:s|d)?\s+over|heads|headed|directs|directed)\b", re.IGNORECASE),
        ],
        [
            re.compile(r"\b(?:(?:is|was)\s+led\s+by|(?:is|was)\s+headed\s+by|(?:is|was)\s+directed\s+by)\b", re.IGNORECASE),
            re.compile(r"\b(?:President|Prime\s+Minister|Premier|Chancellor|Chair|Chairman|Governor|Leader|Foreign\s+Minister|Defence\s+Minister|Secretary\s+of\s+State|Supreme\s+Leader|spokesman|spokesperson|envoy|commander)\b", re.IGNORECASE),
        ],
        0.95,
    ),
    (
        RelationshipType.MEMBER_OF,
        [
            re.compile(r"\b(?:is\s+a\s+member\s+of|joined|belongs\s+to|affiliated\s+with|represented\s+in|member\s+state\s+of|part\s+of|members?\s+of)\b", re.IGNORECASE),
        ],
        [
            re.compile(r"\b(?:includes\s+member|counts\s+as\s+member|members?|allies|nations?)\b", re.IGNORECASE),
        ],
        0.92,
    ),
    (
        RelationshipType.HEADQUARTERED_IN,
        [
            re.compile(r"\b(?:is\s+)?(?:headquartered\s+in|based\s+in)\b", re.IGNORECASE),
        ],
        [
            re.compile(r"\b(?:is\s+the\s+headquarters\s+of|is\s+the\s+home\s+of)\b", re.IGNORECASE),
        ],
        0.94,
    ),
    (
        RelationshipType.LOCATED_IN,
        [
            re.compile(r"\b(?:is\s+)?(?:located\s+in|situated\s+in)\b", re.IGNORECASE),
        ],
        [],
        0.88,
    ),
    (
        RelationshipType.OPERATES_IN,
        [
            re.compile(r"\b(?:operates\s+in|conducts\s+business\s+in|expanded\s+into|maintains\s+operations\s+in|presence\s+in|facilities\s+in|office\s+in|branch\s+in)\b", re.IGNORECASE),
        ],
        [],
        0.90,
    ),
    (
        RelationshipType.BORDERS,
        [
            re.compile(r"\b(?:borders|shares\s+a\s+border\s+with|neighboring|adjacent\s+to|bordering|border\s+with|borders?\s+with|along\s+the\s+border\s+of|frontier\s+with)\b", re.IGNORECASE),
        ],
        [],
        0.96,
    ),
    (
        RelationshipType.SANCTIONS,
        [
            re.compile(r"\b(?:sanctions?|sanctioned|imposed\s+sanctions\s+on|blacklisted|penalized|placed\s+under\s+sanctions|levied\s+sanctions\s+against|tariffs\s+on|trade\s+restrictions\s+on|export\s+controls\s+on|penalties\s+against|curbs\s+on)\b", re.IGNORECASE),
        ],
        [
            re.compile(r"\b(?:was\s+sanctioned\s+by|faced\s+sanctions\s+from|is\s+blacklisted\s+by)\b", re.IGNORECASE),
        ],
        0.94,
    ),
    (
        RelationshipType.ATTACKS,
        [
            re.compile(r"\b(?:attacked|struck|bombed|fired\s+missiles\s+at|launched\s+strikes\s+against|strikes\s+on|missile\s+strikes\s+on|drone\s+strikes\s+on|offensive\s+against|raided|invaded|shelled|assaulted|strikes\s+in|operations\s+against|war\s+against|fire\s+on|clashes\s+with)\b", re.IGNORECASE),
        ],
        [
            re.compile(r"\b(?:was\s+attacked\s+by|was\s+struck\s+by|came\s+under\s+fire\s+from|was\s+bombed\s+by)\b", re.IGNORECASE),
        ],
        0.93,
    ),
    (
        RelationshipType.SUPPORTS,
        [
            re.compile(r"\b(?:supports?|backed|pledged\s+support\s+for|provided\s+aid\s+to|aid\s+to|military\s+aid\s+to|endorsed|funded|reaffirmed\s+support\s+for|aid\s+for|assistance\s+to|backing\s+for|loan\s+to)\b", re.IGNORECASE),
        ],
        [
            re.compile(r"\b(?:is\s+supported\s+by|was\s+backed\s+by|received\s+aid\s+from|was\s+endorsed\s+by)\b", re.IGNORECASE),
        ],
        0.91,
    ),
    (
        RelationshipType.OPPOSES,
        [
            re.compile(r"\b(?:opposes?|condemned|denounced|criticized|rejected\s+claims\s+by|warned\s+against|threatened|protested\s+against|rebuked|dismissed\s+claims\s+by|warning\s+to)\b", re.IGNORECASE),
        ],
        [
            re.compile(r"\b(?:was\s+condemned\s+by|was\s+denounced\s+by|faced\s+criticism\s+from)\b", re.IGNORECASE),
        ],
        0.89,
    ),
    (
        RelationshipType.NEGOTIATES_WITH,
        [
            re.compile(r"\b(?:held\s+talks\s+with|negotiates\s+with|in\s+discussions\s+with|met\s+with|meets\s+with|spoke\s+with|visited|dialogue\s+with|engaged\s+in\s+talks\s+with|summit\s+with|hosted|talks\s+between|meeting\s+with|conferred\s+with|discussion\s+with)\b", re.IGNORECASE),
        ],
        [],
        0.90,
    ),
    (
        RelationshipType.SIGNED_AGREEMENT_WITH,
        [
            re.compile(r"\b(?:signed\s+(?:an?\s+)?agreement\s+with|inked\s+a\s+deal\s+with|reached\s+an\s+accord\s+with|ratified\s+treaty\s+with|signed\s+pact\s+with|signed\s+accord\s+with|deal\s+between|pact\s+between|agreement\s+between)\b", re.IGNORECASE),
        ],
        [],
        0.95,
    ),
    (
        RelationshipType.TRADES_WITH,
        [
            re.compile(r"\b(?:trades\s+with|trade\s+with|bilateral\s+trade\s+with|commercial\s+ties\s+with|trade\s+partner\s+of|conducts\s+trade\s+with|economic\s+ties\s+with|supplies\s+energy\s+to|trade\s+between|exports\s+to|imports\s+from|ships\s+to|supplies\s+to)\b", re.IGNORECASE),
        ],
        [],
        0.91,
    ),
    (
        RelationshipType.ALLIED_WITH,
        [
            re.compile(r"\b(?:signed\s+(?:a\s+)?security\s+pact\s+with|formed\s+an\s+alliance\s+with|is\s+an\s+ally\s+of|strategic\s+partner\s+of|partnered\s+with|allies\s+with|strategic\s+ties\s+with|ties\s+with|bilateral\s+ties\s+with|relations\s+with|ties\s+between|alliance\s+between|partner\s+of|cooperation\s+with|partnership\s+with)\b", re.IGNORECASE),
        ],
        [],
        0.90,
    ),
    (
        RelationshipType.GOVERNS,
        [
            re.compile(r"\b(?:governs|regulates|manages\s+monetary\s+policy\s+for|issues|controls\s+the\s+supply\s+of|central\s+bank\s+of|monetary\s+policy\s+for|raised\s+rates|cut\s+rates|holds\s+rates|interest\s+rates|rates)\b", re.IGNORECASE),
        ],
        [
            re.compile(r"\b(?:is\s+governed\s+by|is\s+regulated\s+by|is\s+issued\s+by)\b", re.IGNORECASE),
        ],
        0.95,
    ),
    (
        RelationshipType.PRODUCES,
        [
            re.compile(r"\b(?:produces|refines|mines|extracts|manufactures|major\s+producer\s+of|output\s+of|producer\s+of|exporter\s+of|supplies)\b", re.IGNORECASE),
        ],
        [
            re.compile(r"\b(?:is\s+produced\s+by|is\s+refined\s+by|is\s+mined\s+by|from)\b", re.IGNORECASE),
        ],
        0.91,
    ),
    (
        RelationshipType.OWNS,
        [
            re.compile(r"\b(?:owns|acquired|purchased|holds\s+(?:a\s+)?stake\s+in|subsidiary|parent\s+company\s+of)\b", re.IGNORECASE),
        ],
        [
            re.compile(r"\b(?:is\s+owned\s+by|was\s+acquired\s+by|subsidiary\s+of)\b", re.IGNORECASE),
        ],
        0.93,
    ),
    (
        RelationshipType.EXPORTS,
        [
            re.compile(r"\b(?:exports|ships|supplies|major\s+exporter\s+of|exporting)\b", re.IGNORECASE),
        ],
        [
            re.compile(r"\b(?:is\s+exported\s+by)\b", re.IGNORECASE),
        ],
        0.91,
    ),
]

_NEGATION_REGEX = re.compile(
    r"\b(?:not|never|neither|nor|no\s+longer|denied\s+that|refuted\s+claims|falsely\s+claimed|does\s+not|is\s+not|was\s+not|did\s+not|cannot)\b",
    re.IGNORECASE,
)

_HISTORICAL_REGEX = re.compile(
    r"\b(?:former|past|ex-|previously|historically|once|prior)\b",
    re.IGNORECASE,
)

_HEDGING_REGEX = re.compile(
    r"\b(?:rumored|speculated|allegedly|reportedly|unconfirmed|unverified|claims|purportedly)\b",
    re.IGNORECASE,
)


class DeterministicRelationshipExtractor:
    """High-precision, explainable relationship extraction engine using deterministic syntax patterns."""

    def __init__(self, extractor_version: str = "v0.7.0"):
        self.extractor_version = extractor_version

    def extract_relationships_from_sentence(
        self,
        sentence: str,
        entities: List[Dict[str, Any]],
        document_id: Optional[UUID] = None,
        event_id: Optional[UUID] = None,
    ) -> List[EntityRelationshipCreate]:
        """Extract evidence-backed entity relationships from a single sentence."""
        relationships: List[EntityRelationshipCreate] = []
        if len(entities) < 2:
            return relationships

        # Check for sentence-level negation
        is_negated = bool(_NEGATION_REGEX.search(sentence))
        is_historical = bool(_HISTORICAL_REGEX.search(sentence))
        is_hedged = bool(_HEDGING_REGEX.search(sentence))

        # Collect all entity mentions in sentence using surface forms and aliases
        all_mentions: List[Tuple[int, int, Dict[str, Any]]] = []
        for ent in entities:
            cname = ent.get("canonical_name", "")
            aliases = list(_CANONICAL_ALIASES_MAP.get(cname, []))
            if cname and cname not in aliases:
                aliases.append(cname)

            for alias in aliases:
                if not alias or len(alias) < 2:
                    continue
                # Use word boundaries so short aliases don't false-match substrings
                pattern = rf"\b{re.escape(alias)}\b"
                for m in re.finditer(pattern, sentence, re.IGNORECASE):
                    all_mentions.append((m.start(), m.end(), ent))

        # Clause boundary regex (allow commas in standard phrases while catching major subordinating clauses)
        clause_break_regex = re.compile(r";\s*|,\s*(?:while|whereas|although|however)\b", re.IGNORECASE)

        # Check all entity pairs (Order matters!)
        for i in range(len(entities)):
            for j in range(len(entities)):
                if i == j:
                    continue
                ent_a = entities[i]
                ent_b = entities[j]

                name_a = ent_a.get("canonical_name", "")
                name_b = ent_b.get("canonical_name", "")
                id_a = ent_a.get("id")
                id_b = ent_b.get("id")

                if not id_a or not id_b or not name_a or not name_b:
                    continue

                matches_a = [m for m in all_mentions if m[2].get("id") == id_a]
                matches_b = [m for m in all_mentions if m[2].get("id") == id_b]

                if not matches_a or not matches_b:
                    continue

                for start_a, end_a, _ in matches_a:
                    for start_b, end_b, _ in matches_b:
                        # Text span between the two entities
                        if end_a <= start_b:
                            between_text = sentence[end_a:start_b]

                            # 1. Skip if text between is excessively long
                            if len(between_text.strip()) > 75:
                                continue

                            # 2. Skip if another entity intervenes between A and B
                            intervening = any(
                                (m_start >= end_a and m_end <= start_b and m_ent.get("id") not in (id_a, id_b))
                                for m_start, m_end, m_ent in all_mentions
                            )
                            if intervening:
                                continue

                            # 3. Skip if a cross-clause boundary separates A and B
                            if clause_break_regex.search(between_text):
                                continue

                            # 4. If negation appears between entities, reject
                            if _NEGATION_REGEX.search(between_text):
                                continue

                            for rel_type, active_patterns, passive_patterns, base_conf in _RELATIONSHIP_RULES:
                                # Active patterns: A is predicate of B
                                for pat in active_patterns:
                                    if pat.search(between_text):
                                        if is_negated and _NEGATION_REGEX.search(sentence[:end_b]):
                                            continue  # Negated relation

                                        conf = base_conf
                                        if is_hedged:
                                            conf -= 0.35  # Penalize hedging

                                        # Validate entity type compatibility
                                        if not self._is_compatible(ent_a, ent_b, rel_type):
                                            continue

                                        relationships.append(
                                            EntityRelationshipCreate(
                                                source_entity_id=id_a,
                                                target_entity_id=id_b,
                                                relationship_type=rel_type,
                                                confidence=round(max(0.0, min(1.0, conf)), 2),
                                                source_document_id=document_id,
                                                source_event_id=event_id,
                                                extraction_method="deterministic_rules_v0.7",
                                                extractor_version=self.extractor_version,
                                                evidence=sentence.strip(),
                                                metadata_={
                                                    "historical": is_historical,
                                                    "hedged": is_hedged,
                                                    "span": [start_a, end_b],
                                                    "direction": "active",
                                                },
                                            )
                                        )

                                # Passive patterns: B is predicate of A (inverted direction)
                                for pat in passive_patterns:
                                    if pat.search(between_text):
                                        if is_negated and _NEGATION_REGEX.search(sentence[:end_b]):
                                            continue  # Negated

                                        conf = base_conf
                                        if is_hedged:
                                            conf -= 0.35

                                        # In passive, target is actually the agent (source of the relationship)
                                        if not self._is_compatible(ent_b, ent_a, rel_type):
                                            continue

                                        relationships.append(
                                            EntityRelationshipCreate(
                                                source_entity_id=id_b,
                                                target_entity_id=id_a,
                                                relationship_type=rel_type,
                                                confidence=round(max(0.0, min(1.0, conf)), 2),
                                                source_document_id=document_id,
                                                source_event_id=event_id,
                                                extraction_method="deterministic_rules_v0.7",
                                                extractor_version=self.extractor_version,
                                                evidence=sentence.strip(),
                                                metadata_={
                                                    "historical": is_historical,
                                                    "hedged": is_hedged,
                                                    "span": [start_a, end_b],
                                                    "direction": "passive_inverted",
                                                },
                                            )
                                        )

        # Deduplicate relationships by (source, target, rel_type), keeping highest confidence
        unique_map: Dict[Tuple[UUID, UUID, RelationshipType], EntityRelationshipCreate] = {}
        for r in relationships:
            key = (r.source_entity_id, r.target_entity_id, r.relationship_type)
            if key not in unique_map or r.confidence > unique_map[key].confidence:
                unique_map[key] = r

        return list(unique_map.values())

    def _is_compatible(
        self,
        source_entity: Dict[str, Any],
        target_entity: Dict[str, Any],
        rel_type: RelationshipType,
    ) -> bool:
        """Enforce semantic ontology constraints to avoid type-incompatible relationships."""
        src_type = (source_entity.get("entity_type") or "").upper()
        tgt_type = (target_entity.get("entity_type") or "").upper()

        if rel_type == RelationshipType.LEADS:
            # Person -> Country, Gov, Org, Central Bank, Company, International Org
            if src_type == "PERSON" and tgt_type in ("COUNTRY", "GOVERNMENT", "ORGANIZATION", "CENTRAL_BANK", "GOVERNMENT_AGENCY", "COMPANY", "INTERNATIONAL_ORGANIZATION"):
                return True
            if src_type in ("COUNTRY", "GOVERNMENT") and tgt_type in ("ORGANIZATION", "INTERNATIONAL_ORGANIZATION"):
                return True
            if src_type in ("ORGANIZATION", "COMPANY") and tgt_type in ("ORGANIZATION", "INTERNATIONAL_ORGANIZATION"):
                return True
            return False

        if rel_type == RelationshipType.MEMBER_OF:
            if src_type in ("COUNTRY", "PERSON", "ORGANIZATION", "COMPANY") and tgt_type in ("INTERNATIONAL_ORGANIZATION", "ORGANIZATION", "GOVERNMENT"):
                return True
            return False

        if rel_type in (RelationshipType.HEADQUARTERED_IN, RelationshipType.OPERATES_IN):
            # Org / Company / Central Bank / Int Org -> Location / Country / City
            if src_type in ("ORGANIZATION", "CENTRAL_BANK", "GOVERNMENT_AGENCY", "COMPANY", "INTERNATIONAL_ORGANIZATION") and tgt_type in ("LOCATION", "COUNTRY", "CITY"):
                return True
            return False

        if rel_type == RelationshipType.OWNS:
            # Company/Org -> Company/Org
            if src_type in ("ORGANIZATION", "COMPANY", "GOVERNMENT_AGENCY") and tgt_type in ("ORGANIZATION", "COMPANY"):
                return True
            return False

        if rel_type == RelationshipType.GOVERNS:
            # Central Bank / Gov -> Currency
            if src_type in ("CENTRAL_BANK", "GOVERNMENT_AGENCY") and tgt_type in ("CURRENCY", "COMMODITY"):
                return True
            return False

        if rel_type in (RelationshipType.PRODUCES, RelationshipType.EXPORTS):
            # Org/Country -> Commodity
            if src_type in ("ORGANIZATION", "COMPANY", "COUNTRY") and tgt_type in ("COMMODITY", "SECTOR"):
                return True
            return False

        if rel_type == RelationshipType.ALLIED_WITH:
            if src_type in ("COUNTRY", "ORGANIZATION", "GOVERNMENT") and tgt_type in ("COUNTRY", "ORGANIZATION", "GOVERNMENT"):
                return True
            return False

        return True
