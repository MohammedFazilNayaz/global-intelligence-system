"""
Deterministic, evidence-backed Economic Intelligence Extraction Engine.
Implements V0.5 controlled taxonomy, zero-fabrication numerical parsing,
value semantics (reported vs previous vs expected vs revised),
central bank intelligence, and explainable economic relevance scoring.
"""

import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from backend.app.schemas.economic import (
    EconomicDomain,
    IndicatorType,
    CentralBankDecisionType,
    ObservationDirection,
    ExtractedEconomicObservation,
    INDICATOR_DOMAIN_MAP,
)


# ---------------------------------------------------------------------------
# Country / Region Normalization Mapping
# ---------------------------------------------------------------------------
_COUNTRY_ALIAS_MAP: Dict[str, Tuple[str, str]] = {
    # alias (lowercased) -> (canonical_name, country_code)
    "us": ("United States", "US"),
    "u.s.": ("United States", "US"),
    "united states": ("United States", "US"),
    "america": ("United States", "US"),
    "american": ("United States", "US"),
    "federal reserve": ("United States", "US"),
    "the fed": ("United States", "US"),
    "fed": ("United States", "US"),
    "eurozone": ("Eurozone", "EU"),
    "euro zone": ("Eurozone", "EU"),
    "euro area": ("Eurozone", "EU"),
    "european union": ("Eurozone", "EU"),
    "eu": ("Eurozone", "EU"),
    "european central bank": ("Eurozone", "EU"),
    "ecb": ("Eurozone", "EU"),
    "uk": ("United Kingdom", "GB"),
    "u.k.": ("United Kingdom", "GB"),
    "united kingdom": ("United Kingdom", "GB"),
    "britain": ("United Kingdom", "GB"),
    "british": ("United Kingdom", "GB"),
    "bank of england": ("United Kingdom", "GB"),
    "boe": ("United Kingdom", "GB"),
    "japan": ("Japan", "JP"),
    "japanese": ("Japan", "JP"),
    "bank of japan": ("Japan", "JP"),
    "boj": ("Japan", "JP"),
    "tokyo": ("Japan", "JP"),
    "germany": ("Germany", "DE"),
    "german": ("Germany", "DE"),
    "china": ("China", "CN"),
    "chinese": ("China", "CN"),
    "peoples bank of china": ("China", "CN"),
    "pboc": ("China", "CN"),
    "india": ("India", "IN"),
    "indian": ("India", "IN"),
    "reserve bank of india": ("India", "IN"),
    "rbi": ("India", "IN"),
    "opec": ("OPEC", "XW"),
    "opec+": ("OPEC+", "XW"),
    "global": ("Global", "GL"),
}


# ---------------------------------------------------------------------------
# Indicator Catalog & Trigger Definitions
# ---------------------------------------------------------------------------
# (IndicatorType, canonical_name_template, default_unit, triggers, tier_weight)
_INDICATOR_DEFINITIONS: List[Tuple[IndicatorType, str, str, List[str], float]] = [
    (
        IndicatorType.CPI,
        "{country} Consumer Price Index (CPI)",
        "%",
        ["consumer price index", "cpi", "headline cpi", "core cpi", "consumer prices"],
        0.92,
    ),
    (
        IndicatorType.INFLATION,
        "{country} Inflation Rate",
        "%",
        ["headline inflation", "inflation rate", "annual inflation", "annualized inflation", "inflation"],
        0.90,
    ),
    (
        IndicatorType.PPI,
        "{country} Producer Price Index (PPI)",
        "%",
        ["producer price index", "ppi", "producer prices", "wholesale prices"],
        0.78,
    ),
    (
        IndicatorType.GDP,
        "{country} Gross Domestic Product (GDP)",
        "%",
        ["gross domestic product", "gdp", "economic growth", "economic contraction", "quarterly gdp"],
        0.94,
    ),
    (
        IndicatorType.UNEMPLOYMENT,
        "{country} Unemployment Rate",
        "%",
        ["unemployment rate", "jobless rate", "unemployment", "jobless claims"],
        0.86,
    ),
    (
        IndicatorType.PAYROLLS,
        "{country} Non-Farm Payrolls",
        "count",
        ["non-farm payrolls", "nonfarm payrolls", "payrolls", "jobs added", "employment gains"],
        0.90,
    ),
    (
        IndicatorType.WAGES,
        "{country} Average Hourly Earnings / Wage Growth",
        "%",
        ["average hourly earnings", "wage growth", "wages", "labor costs"],
        0.80,
    ),
    (
        IndicatorType.CENTRAL_BANK_RATE,
        "{country} Policy / Benchmark Interest Rate",
        "%",
        [
            "benchmark interest rate", "benchmark rate", "benchmark rates", "policy rate",
            "fed funds rate", "federal funds rate", "deposit facility rate",
            "repo rate", "main refinancing rate", "interest rate",
        ],
        0.95,
    ),
    (
        IndicatorType.RETAIL_SALES,
        "{country} Retail Sales",
        "%",
        ["retail sales", "retail sales volumes", "consumer spending"],
        0.80,
    ),
    (
        IndicatorType.INDUSTRIAL_PRODUCTION,
        "{country} Industrial Production",
        "%",
        ["industrial production", "factory output", "industrial output"],
        0.76,
    ),
    (
        IndicatorType.PMI,
        "{country} Purchasing Managers Index (PMI)",
        "pts",
        ["purchasing managers index", "pmi", "manufacturing pmi", "services pmi", "composite pmi"],
        0.78,
    ),
    (
        IndicatorType.BUSINESS_CONFIDENCE,
        "{country} Business Confidence / Climate Index",
        "pts",
        ["business climate index", "ifo business climate", "business confidence", "economic sentiment"],
        0.72,
    ),
    (
        IndicatorType.CONSUMER_CONFIDENCE,
        "{country} Consumer Confidence Index",
        "pts",
        ["consumer confidence index", "consumer confidence", "consumer sentiment"],
        0.74,
    ),
    (
        IndicatorType.TRADE_BALANCE,
        "{country} Trade Balance",
        "currency",
        ["trade balance", "trade deficit", "trade surplus"],
        0.82,
    ),
    (
        IndicatorType.EXPORTS,
        "{country} Exports",
        "%",
        ["exports", "export volumes"],
        0.75,
    ),
    (
        IndicatorType.IMPORTS,
        "{country} Imports",
        "%",
        ["imports", "import volumes"],
        0.75,
    ),
    (
        IndicatorType.PUBLIC_DEFICIT,
        "{country} Government Budget Deficit",
        "currency",
        ["budget deficit", "fiscal deficit", "federal budget deficit", "public deficit"],
        0.82,
    ),
    (
        IndicatorType.GOVERNMENT_DEBT,
        "{country} Government Debt",
        "currency",
        ["national debt", "government debt", "public debt", "debt to gdp"],
        0.80,
    ),
    (
        IndicatorType.OIL,
        "Crude Oil Output & Quotas",
        "bbl",
        ["crude oil output", "crude output", "oil production cuts", "oil output", "oil production"],
        0.85,
    ),
]


# ---------------------------------------------------------------------------
# Regular Expressions for Numerical Parsing & Value Semantics
# ---------------------------------------------------------------------------

# Release / reporting action verbs indicating an actual event, not passing mention
_RELEASE_VERBS = re.compile(
    r"\b(?:rose|climbed|surged|jumped|increased|expanded|grew|ticked\s+up|"
    r"fell|dropped|declined|slid|slipped|contracted|slowed|eased|ticked\s+down|"
    r"held|holds|maintained|left\s+unchanged|stands\s+at|hit|hits|narrowed|widened|"
    r"raised|raises|hiking|hikes|cut|cuts|cutting|lowered|lowers|"
    r"reported|reports|accelerated|moderated|totaled|settled\s+at|agreed\s+to)\b",
    re.IGNORECASE,
)

# Number with unit: e.g. 3.2%, 25 bps, 5.25%-5.50%, $1.9 trillion, 142,000, 86.6, 621 billion yen
_PERCENT_REGEX = re.compile(r"(\b\d+(?:\.\d+)?)\s*(?:%|\bpercent\b|\bpercentage\s+points?\b)", re.IGNORECASE)
_RANGE_PERCENT_REGEX = re.compile(r"(\b\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)?\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)", re.IGNORECASE)
_BPS_REGEX = re.compile(r"(\b\d+(?:\.\d+)?)\s*(?:basis\s+points?|bps)\b", re.IGNORECASE)
_INDEX_PTS_REGEX = re.compile(r"\b(?:to|at|hit|dropped\s+to|rose\s+to)\s+(\d{2,3}(?:\.\d+)?)\s*(?:points|pts)?\b", re.IGNORECASE)
_CURRENCY_AMOUNT_REGEX = re.compile(
    r"(?:(\$|€|£|¥)\s*(\d+(?:\.\d+)?)\s*(trillion|billion|million)?|"
    r"(\d+(?:\.\d+)?)\s*(trillion|billion|million)?\s*(yen|euros|dollars|pounds))\b",
    re.IGNORECASE,
)
_COUNT_REGEX = re.compile(r"\b(?:by|of|to)\s+(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?\s*(?:million|thousand|k))\b", re.IGNORECASE)

# Observation Period: e.g. August, July 2026, Q2, second quarter, year-over-year
_PERIOD_REGEX = re.compile(
    r"\b(?:in|for|during)\s+("
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"(?:\s+\d{4})?|"
    r"Q[1-4](?:\s+\d{4})?|"
    r"(?:first|second|third|fourth)\s+quarter(?:\s+of\s+\d{4})?|"
    r"fiscal\s+year\s+\d{4})\b|"
    r"\b(year-over-year|yoy|month-over-month|mom)\b",
    re.IGNORECASE,
)

# Previous Value Extraction
_PREVIOUS_VALUE_PATTERNS = [
    re.compile(r"\b(?:from|compared\s+(?:to|with)|versus)\s+(?:a\s+)?(\d+(?:\.\d+)?)\s*(trillion|billion|million)?\s*(yen|dollars|euros|pounds)\s*(?:a\s+year\s+earlier|previously)?", re.IGNORECASE),
    re.compile(r"\b(?:from|compared\s+with|versus|up\s+from|down\s+from)\s+(?:a\s+)?(\d+(?:\.\d+)?)\s*(?:%|\bpercent\b|\bpercentage\s+points?\b)\s*(?:previously|prior|in\s+[A-Za-z]+)?", re.IGNORECASE),
    re.compile(r"\b(?:from|compared\s+with|versus)\s+(\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)?\s*(?:in\s+[A-Za-z]+|a\s+year\s+earlier|prior\s+month|previously)", re.IGNORECASE),
    re.compile(r"\bprior\s+month['’]?s\s+(\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)?", re.IGNORECASE),
    re.compile(r"\brebounding\s+from\s+(?:a\s+)?(-?\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)", re.IGNORECASE),
    re.compile(r"\b(?:from|down\s+from|up\s+from)\s+(?:a\s+)?(\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)?", re.IGNORECASE),
]

# Expected / Consensus Value Extraction
_EXPECTED_VALUE_PATTERNS = [
    re.compile(r"\b(?:below|above|beating|missing|matching|versus|against)\s+(?:consensus\s+)?expectations?\s+of\s+(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)?", re.IGNORECASE),
    re.compile(r"\b(?:consensus\s+forecast|analysts?\s+expected|forecast\s+of)\s+(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)?", re.IGNORECASE),
    re.compile(r"\bversus\s+consensus\s+(?:expectations?\s+)?(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)?", re.IGNORECASE),
]

# Revised Value Extraction
_REVISED_VALUE_PATTERNS = [
    re.compile(r"\bwere\s+revised\s+(?:down|up)\s+to\s+(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)?\s+from\s+(?:the\s+initially\s+reported\s+)?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"\b(?:upward|downward)\s+revision\s+from\s+(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s+to\s+(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)", re.IGNORECASE),
]

# Central Bank Action Keywords
_CB_HIKE_REGEX = re.compile(
    r"\b(?:raised|raises|raising|hiked|hikes|hiking|increases?|lifted|lifts)\s+(?:its\s+)?(?:[\w-]+\s+){0,4}rates?\b",
    re.IGNORECASE,
)
_CB_CUT_REGEX = re.compile(
    r"\b(?:cut|cuts|cutting|lowered|lowers|lowering|reduced|reduces)\s+(?:its\s+)?(?:[\w-]+\s+){0,4}rates?\b",
    re.IGNORECASE,
)
_CB_HOLD_REGEX = re.compile(
    r"\b(?:holds?|held|maintains?|maintained|leaves?\s+unchanged|left\s+unchanged|steady|pause|paused)\s+(?:its\s+)?(?:[\w-]+\s+){0,4}rates?\b",
    re.IGNORECASE,
)


class DeterministicEconomicExtractor:
    """Deterministic, rule-based extraction engine for V0.5 Economic Intelligence."""

    def __init__(self):
        self.version = "deterministic_economic_v0.5"

    def extract_economic_intelligence(
        self,
        text: str,
        published_at: Optional[datetime] = None,
    ) -> List[ExtractedEconomicObservation]:
        """Extract structured economic observations with verified value semantics."""
        if not text:
            return []

        # 1. Reject purely historical or retrospective documents (e.g. "Remembering the Volcker shock in 1981")
        if self._is_historical_retrospective(text):
            return []

        observations: List[ExtractedEconomicObservation] = []
        clauses = self._split_clauses(text)

        for clause in clauses:
            clause_clean = clause.strip()
            if not clause_clean:
                continue

            # Check negation: if clause is a confirmed negation, do not extract as positive release
            if self._is_sentence_negated(clause_clean):
                continue

            # Must contain an active release/reporting verb or explicit decision verb
            if not _RELEASE_VERBS.search(clause_clean):
                continue

            # Identify matching indicators in the clause
            matched_indicators = self._match_indicators(clause_clean)
            if not matched_indicators:
                continue

            # Resolve country / jurisdiction context (try clause first, fallback to text)
            country_name, country_code = self._resolve_country(clause_clean)
            if country_name == "Global":
                country_name, country_code = self._resolve_country(text)

            # Extract observation period
            period = self._extract_period(clause_clean) or self._extract_period(text)

            for ind_type, ind_tmpl, default_unit, base_weight in matched_indicators:
                obs = self._extract_observation_for_indicator(
                    sentence=clause_clean,
                    indicator_type=ind_type,
                    indicator_tmpl=ind_tmpl,
                    default_unit=default_unit,
                    base_weight=base_weight,
                    country_name=country_name,
                    country_code=country_code,
                    period=period,
                    published_at=published_at,
                )
                if obs:
                    observations.append(obs)

        return observations

    def _split_clauses(self, text: str) -> List[str]:
        # Split on sentence boundaries and compound clauses (e.g. ', while ', '; ')
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
        clauses = []
        for s in sentences:
            sub = re.split(r"(?:;\s*|,\s*(?:while|whereas|as|meanwhile)\s+)", s, flags=re.IGNORECASE)
            clauses.extend(sub)
        return clauses

    def _is_historical_retrospective(self, text: str) -> bool:
        low = text.lower()
        if re.search(r"\b(?:remembering|retrospective|looking back on|decades ago|in the 19\d{2}s?)\b", low):
            # If the headline or main sentence focuses on historical events from decades ago
            if re.search(r"\b(19\d{2}|200[0-9]|201[0-5])\b", low):
                return True
        return False

    def _is_sentence_negated(self, sentence: str) -> bool:
        low = sentence.lower()
        # Look for explicit negation of central bank or economic action
        neg_patterns = [
            r"\b(?:will\s+not|won'?t|not\s+expected\s+to|denied|ruled\s+out|no\s+plans\s+to|no\s+intention\s+to|refused\s+to)\b",
            r"\b(?:confirmed\s+it\s+will\s+not|decided\s+not\s+to)\b",
        ]
        for pat in neg_patterns:
            if re.search(pat, low):
                return True
        return False

    def _resolve_country(self, text: str) -> Tuple[str, str]:
        """Resolve primary affected country/region from text."""
        low = text.lower()
        for alias, (c_name, c_code) in _COUNTRY_ALIAS_MAP.items():
            # Exact word boundary match
            if re.search(rf"\b{re.escape(alias)}\b", low):
                return c_name, c_code
        return "Global", "GL"

    def _extract_period(self, text: str) -> Optional[str]:
        m = _PERIOD_REGEX.search(text)
        if m:
            val = m.group(1) or m.group(2)
            return val.strip() if val else None
        return None

    def _match_indicators(
        self, sentence: str
    ) -> List[Tuple[IndicatorType, str, str, float]]:
        low = sentence.lower()
        matched = []
        for ind_type, tmpl, d_unit, triggers, weight in _INDICATOR_DEFINITIONS:
            for trig in triggers:
                if re.search(rf"\b{re.escape(trig)}\b", low):
                    matched.append((ind_type, tmpl, d_unit, weight))
                    break
        return matched

    def _extract_observation_for_indicator(
        self,
        sentence: str,
        indicator_type: IndicatorType,
        indicator_tmpl: str,
        default_unit: str,
        base_weight: float,
        country_name: str,
        country_code: str,
        period: Optional[str],
        published_at: Optional[datetime],
    ) -> Optional[ExtractedEconomicObservation]:
        """Extract exact numerical values, revisions, expectations, and relevance."""
        canonical_name = indicator_tmpl.format(country=country_name)
        domain = INDICATOR_DOMAIN_MAP.get(indicator_type, EconomicDomain.GROWTH)

        # 1. Value Semantics
        reported_val: Optional[float] = None
        reported_unit: Optional[str] = default_unit
        previous_val: Optional[float] = None
        expected_val: Optional[float] = None
        revised_val: Optional[float] = None
        direction: Optional[str] = None
        calculation_method: Optional[str] = None

        # --- A. Check for Explicit Revisions first ---
        # e.g. "were revised down to 89,000 from the initially reported 114,000"
        for rev_pat in _REVISED_VALUE_PATTERNS:
            m_rev = rev_pat.search(sentence)
            if m_rev:
                # Group 1 is revised to, Group 2 is from
                val_to_str = m_rev.group(1).replace(",", "")
                val_from_str = m_rev.group(2).replace(",", "") if m_rev.lastindex >= 2 else None
                try:
                    reported_val = float(val_to_str)
                    if val_from_str:
                        previous_val = float(val_from_str)
                        revised_val = reported_val
                    calculation_method = "explicitly_reported"
                    direction = "decrease" if previous_val and reported_val < previous_val else "increase"
                except ValueError:
                    pass
                break

        # --- B. Parse Central Bank Rate Decisions ---
        cb_decision_info: Optional[Dict[str, Any]] = None
        if indicator_type in (IndicatorType.CENTRAL_BANK_RATE, IndicatorType.INTEREST_RATE):
            cb_decision_info, cb_reported, cb_prev, cb_dir = self._parse_central_bank_decision(sentence)
            if cb_reported is not None and reported_val is None:
                reported_val = cb_reported
                reported_unit = "%"
            if cb_prev is not None and previous_val is None:
                previous_val = cb_prev
            if cb_dir:
                direction = cb_dir

        # --- C. Parse Reported Value if not already set ---
        if reported_val is None:
            reported_val, reported_unit, direction_found = self._parse_reported_value(sentence, indicator_type)
            if direction_found and direction is None:
                direction = direction_found

        # --- D. Parse Previous Value if not already set ---
        if previous_val is None:
            previous_val = self._parse_previous_value(sentence)

        # --- E. Parse Expected / Consensus Value ---
        expected_val = self._parse_expected_value(sentence)

        # If no numerical value could be parsed, do NOT fabricate a fake observation
        if reported_val is None and previous_val is None and expected_val is None and not cb_decision_info:
            return None

        # Verbal direction from reporting verbs in the sentence
        verbal_direction = None
        low_s = sentence.lower()
        if re.search(r"\b(?:rose|climbed|surged|jumped|increased|expanded|grew|ticked\s+up|hike|hikes|widened)\b", low_s):
            verbal_direction = "increase"
        elif re.search(r"\b(?:fell|dropped|declined|slid|slipped|contracted|slowed|eased|ticked\s+down|cut|cuts|narrowed)\b", low_s):
            verbal_direction = "decrease"
        elif re.search(r"\b(?:held|steady|unchanged|pause|paused)\b", low_s):
            verbal_direction = "unchanged"

        # --- F. Compute Derived Change (Strict Value Semantics) ---
        change_val: Optional[float] = None
        change_pct: Optional[float] = None
        if reported_val is not None and previous_val is not None:
            # Mathematical difference
            diff = reported_val - previous_val
            change_val = round(diff, 4)
            if calculation_method is None:
                calculation_method = "derived_difference"

            if direction is None:
                if "rebound" in low_s:
                    direction = "increase"
                elif diff > 0:
                    direction = "increase"
                elif diff < 0:
                    direction = "decrease"
                else:
                    direction = "unchanged"

            # Percentage change (only valid if previous is non-zero and not a rate ratio where percentage point makes sense)
            if previous_val != 0:
                change_pct = round((diff / abs(previous_val)) * 100.0, 2)
        elif direction is None:
            direction = verbal_direction

        # --- G. Compute Explainable Economic Relevance Score ---
        relevance, explanation = self._calculate_economic_relevance(
            base_weight=base_weight,
            country_code=country_code,
            reported_val=reported_val,
            expected_val=expected_val,
            change_val=change_val,
            cb_decision_info=cb_decision_info,
        )

        return ExtractedEconomicObservation(
            indicator_type=indicator_type.value,
            indicator_canonical_name=canonical_name,
            economic_domain=domain.value,
            country_name=country_name,
            country_code=country_code,
            observation_period=period,
            observation_date=published_at,
            reported_value=reported_val,
            reported_unit=reported_unit,
            previous_value=previous_val,
            expected_value=expected_val,
            revised_value=revised_val,
            direction=direction,
            change_value=change_val,
            change_percent=change_pct,
            calculation_method=calculation_method,
            economic_relevance=relevance,
            evidence_snippet=sentence[:250],
            central_bank_decision=cb_decision_info,
            metadata={
                "relevance_explanation": explanation,
                "evidence_snippet": sentence,
                "extractor": self.version,
            },
        )

    def _parse_reported_value(
        self, sentence: str, indicator_type: IndicatorType
    ) -> Tuple[Optional[float], Optional[str], Optional[str]]:
        """Parse reported number and unit from sentence without fabrication."""
        # 1. Percent range (e.g. 5.25%-5.50%)
        m_rng = _RANGE_PERCENT_REGEX.search(sentence)
        if m_rng:
            try:
                # Take upper bound or mid
                v2 = float(m_rng.group(2))
                return v2, "%", None
            except ValueError:
                pass

        # 2. Basis points (e.g. 25 bps, 50 basis points)
        m_bps = _BPS_REGEX.search(sentence)
        if m_bps:
            try:
                bps_val = float(m_bps.group(1))
                return bps_val, "bps", None
            except ValueError:
                pass

        # 3. Currency / Count (e.g. $1.9 trillion, 621 billion yen, 142,000)
        m_cur = _CURRENCY_AMOUNT_REGEX.search(sentence)
        if m_cur:
            # Group 1 is symbol, Group 2 is num, Group 3 is mult
            # Or Group 4 is num, Group 5 is mult, Group 6 is currency name
            num_str = m_cur.group(2) or m_cur.group(4)
            mult_str = (m_cur.group(3) or m_cur.group(5) or "").lower()
            unit_str = m_cur.group(1) or m_cur.group(6) or "currency"
            if num_str:
                try:
                    raw_f = float(num_str)
                    if "trillion" in mult_str:
                        raw_f *= 1000.0  # normalize in billions
                        unit_str = f"{unit_str} (billions)"
                    elif "million" in mult_str:
                        raw_f /= 1000.0
                    return raw_f, unit_str, None
                except ValueError:
                    pass

        # 4. Standard percentage (e.g. 3.2%)
        m_pct = _PERCENT_REGEX.search(sentence)
        if m_pct:
            try:
                return float(m_pct.group(1)), "%", None
            except ValueError:
                pass

        # 5. Count / Payroll numbers (e.g. 142,000)
        m_cnt = _COUNT_REGEX.search(sentence)
        if m_cnt:
            cnt_str = m_cnt.group(1).replace(",", "")
            if "thousand" in cnt_str or "k" in cnt_str:
                cnt_str = cnt_str.replace("thousand", "").replace("k", "").strip()
                try:
                    return float(cnt_str) * 1000.0, "count", None
                except ValueError:
                    pass
            try:
                return float(cnt_str), "count", None
            except ValueError:
                pass

        # 6. Index points (e.g. dropped to 86.6)
        m_pts = _INDEX_PTS_REGEX.search(sentence)
        if m_pts:
            try:
                return float(m_pts.group(1)), "pts", None
            except ValueError:
                pass

        # 7. Commodity barrels (e.g. 2.2 million barrels per day)
        m_bbl = re.search(r"(\d+(?:\.\d+)?)\s*million\s+barrels", sentence, re.IGNORECASE)
        if m_bbl:
            try:
                return float(m_bbl.group(1)), "million bbl/d", None
            except ValueError:
                pass

        return None, None, None

    def _parse_previous_value(self, sentence: str) -> Optional[float]:
        """Extract explicit previous value or return None."""
        for pat in _PREVIOUS_VALUE_PATTERNS:
            m = pat.search(sentence)
            if m:
                val_str = m.group(1).replace(",", "")
                try:
                    val = float(val_str)
                    if m.lastindex and m.lastindex >= 2:
                        mult = (m.group(2) or "").lower()
                        if mult == "trillion":
                            val *= 1000.0
                        elif mult == "million":
                            val /= 1000.0
                    return val
                except ValueError:
                    pass
        return None

    def _parse_expected_value(self, sentence: str) -> Optional[float]:
        """Extract explicit consensus/expected value or return None."""
        for pat in _EXPECTED_VALUE_PATTERNS:
            m = pat.search(sentence)
            if m:
                val_str = m.group(1).replace(",", "")
                try:
                    val = float(val_str)
                    return val
                except ValueError:
                    pass
        return None

    def _parse_central_bank_decision(
        self, sentence: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[float], Optional[float], Optional[str]]:
        """Extract structured central bank rate action, rate change bps, and target rate."""
        low = sentence.lower()
        action: Optional[str] = None
        action_type: Optional[str] = None
        target_rate: Optional[float] = None
        prev_rate: Optional[float] = None
        direction: Optional[str] = None

        if _CB_HIKE_REGEX.search(sentence):
            action = "rate_hike"
            action_type = CentralBankDecisionType.RATE_HIKE.value
            direction = ObservationDirection.HIKE.value
        elif _CB_CUT_REGEX.search(sentence):
            action = "rate_cut"
            action_type = CentralBankDecisionType.RATE_CUT.value
            direction = ObservationDirection.CUT.value
        elif _CB_HOLD_REGEX.search(sentence):
            action = "rate_hold"
            action_type = CentralBankDecisionType.RATE_HOLD.value
            direction = ObservationDirection.HOLD.value

        if not action:
            return None, None, None, None

        # Extract target rate: e.g. "to 4.00%" or "to 5.00%" or "steady at 5.25%-5.50%"
        m_rng = _RANGE_PERCENT_REGEX.search(sentence)
        if m_rng and ("to" in sentence.lower() or "at" in sentence.lower() or "steady" in sentence.lower()):
            try:
                target_rate = float(m_rng.group(2))
            except ValueError:
                pass

        if target_rate is None:
            m_target = re.search(r"\b(?:to|at|held\s+at|steady\s+at)\s+(\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)", sentence, re.IGNORECASE)
            if m_target:
                try:
                    target_rate = float(m_target.group(1))
                except ValueError:
                    pass

        # Extract previous rate: e.g. "down from 5.25%"
        m_prev = re.search(r"\b(?:down\s+from|up\s+from|from)\s+(\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)", sentence, re.IGNORECASE)
        if m_prev:
            try:
                prev_rate = float(m_prev.group(1))
            except ValueError:
                pass

        # Extract bps change: e.g. "by 25 basis points"
        m_bps = _BPS_REGEX.search(sentence)
        bps_val: Optional[float] = None
        if m_bps:
            try:
                bps_val = float(m_bps.group(1))
            except ValueError:
                pass

        decision_info = {
            "decision_type": action_type,
            "rate_change_bps": bps_val,
            "target_rate": target_rate,
            "previous_rate": prev_rate,
        }
        return decision_info, target_rate, prev_rate, direction

    def _calculate_economic_relevance(
        self,
        base_weight: float,
        country_code: str,
        reported_val: Optional[float],
        expected_val: Optional[float],
        change_val: Optional[float],
        cb_decision_info: Optional[Dict[str, Any]],
    ) -> Tuple[float, Dict[str, Any]]:
        """Calculate an explainable [0.0, 1.0] economic relevance score with attribution."""
        score = base_weight
        factors: Dict[str, float] = {"base_indicator_tier": round(base_weight, 2)}

        # Geographic scope boost (G7 / major economic bloc)
        if country_code in ("US", "EU", "DE", "JP", "GB", "CN"):
            score += 0.05
            factors["major_economic_jurisdiction"] = 0.05

        # Central bank decision boost
        if cb_decision_info:
            score += 0.04
            factors["central_bank_policy_action"] = 0.04

        # Consensus surprise boost
        if reported_val is not None and expected_val is not None:
            surprise = abs(reported_val - expected_val)
            if surprise > 0:
                score += 0.04
                factors["consensus_variance_surprise"] = 0.04

        # Large shift boost
        if change_val is not None and abs(change_val) >= 0.5:
            score += 0.03
            factors["significant_magnitude_shift"] = 0.03

        final_score = min(1.0, max(0.1, round(score, 2)))
        factors["final_economic_relevance"] = final_score
        return final_score, factors
