from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID
from backend.app.schemas.extraction import ExtractionResult


class BaseIntelligenceExtractor(ABC):
    """Abstract base class for all intelligence extractors.
    
    Any extraction strategy (rule-based, local NLP, external LLM, or specialized models)
    must implement this interface and return an ExtractionResult strictly complying
    with the V0.2 extraction schema contract.
    """

    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version

    @abstractmethod
    def extract(
        self,
        document_id: UUID,
        title: str,
        description: Optional[str] = None,
        content: Optional[str] = None,
        published_at: Optional[datetime] = None,
    ) -> ExtractionResult:
        """Execute extraction over textual document fields and return validated ExtractionResult."""
        pass
