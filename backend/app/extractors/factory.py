from typing import Optional, Dict, Type
from backend.app.extractors.base import BaseIntelligenceExtractor
from backend.app.extractors.rules import RuleBasedIntelligenceExtractor

_EXTRACTOR_REGISTRY: Dict[str, Type[BaseIntelligenceExtractor]] = {
    "rule_based": RuleBasedIntelligenceExtractor,
    "RuleBasedIntelligenceExtractor": RuleBasedIntelligenceExtractor,
}


def get_extractor(name: Optional[str] = None) -> BaseIntelligenceExtractor:
    """Factory retrieving configured or requested intelligence extractor instance."""
    if not name:
        return RuleBasedIntelligenceExtractor()

    extractor_cls = _EXTRACTOR_REGISTRY.get(name)
    if not extractor_cls:
        # Fallback to rule-based extractor
        return RuleBasedIntelligenceExtractor()

    return extractor_cls()
