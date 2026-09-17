import re
import math
from datetime import datetime
from typing import Set, Optional, Tuple, Any
from uuid import UUID

# Comprehensive English stopwords for lexical filtering
ENGLISH_STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "also", "just", "reports", "reported", "said", "says",
    "according", "amid", "following", "hours", "new", "day", "days",
}

TOKEN_PATTERN = re.compile(r"\b[a-zA-Z0-9_\-\.]+\b")


def tokenize_and_normalize(text: Optional[str]) -> Set[str]:
    """Tokenize text into lowercase alphanumeric terms with stopwords and punctuation stripped."""
    if not text:
        return set()
    raw_tokens = TOKEN_PATTERN.findall(text.lower())
    return {
        token.strip(".-_")
        for token in raw_tokens
        if len(token.strip(".-_")) > 1 and token.strip(".-_") not in ENGLISH_STOPWORDS
    }


def jaccard_similarity(set_a: Set[Any], set_b: Set[Any]) -> float:
    """Calculate standard Jaccard index |A ∩ B| / |A ∪ B|."""
    if not set_a or not set_b:
        return 0.0
    union_len = len(set_a | set_b)
    if union_len == 0:
        return 0.0
    return len(set_a & set_b) / union_len


def temporal_proximity_score(
    time_a: Optional[datetime],
    time_b: Optional[datetime],
    max_hours: float = 48.0,
    tau_hours: float = 24.0,
) -> float:
    """Calculate temporal proximity using exponential decay over time delta.
    
    If delta exceeds max_hours (default 48h), score is 0.0 (hard temporal cut).
    Otherwise returns exp(-delta / tau).
    """
    if time_a is None or time_b is None:
        # Neutral fallback when time is missing from one or both
        return 0.5

    delta_seconds = abs((time_a - time_b).total_seconds())
    delta_hours = delta_seconds / 3600.0

    if delta_hours > max_hours:
        return 0.0

    return math.exp(-delta_hours / tau_hours)


def location_similarity_score(
    loc_a_id: Optional[UUID],
    loc_b_id: Optional[UUID],
    country_a: Optional[str] = None,
    country_b: Optional[str] = None,
) -> Tuple[float, bool]:
    """Evaluate event location consistency.
    
    Returns:
        Tuple of (score: float, is_vetoed: bool)
    """
    # 1. Both unassigned (e.g. global macroeconomic indicator, generic policy)
    if loc_a_id is None and loc_b_id is None:
        return 0.7, False

    # 2. One unassigned, one specified -> partial compatibility
    if loc_a_id is None or loc_b_id is None:
        return 0.5, False

    # 3. Exact same canonical entity ID
    if loc_a_id == loc_b_id:
        return 1.0, False

    # 4. Different entity IDs: inspect country codes / geographic hierarchy
    if country_a and country_b:
        if country_a.upper() == country_b.upper():
            # Same sovereign territory (e.g. Kyiv city in Ukraine, or Berlin in Germany)
            return 0.9, False
        else:
            # Conflicting sovereign nations (e.g. Japan vs Ukraine, Chile vs Japan) -> HARD VETO
            return 0.0, True

    # Unknown hierarchy with distinct location IDs
    return 0.2, False
