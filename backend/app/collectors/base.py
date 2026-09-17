from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import time
from backend.app.schemas.document import NormalizedDocument
from backend.app.utils.http_client import ResilientHttpClient
from backend.app.utils.logger import setup_logger

logger = setup_logger("collector.base")


class CollectorError(Exception):
    """Base exception raised during source collection."""
    def __init__(self, source_name: str, message: str, original_exception: Optional[Exception] = None):
        super().__init__(f"Collector [{source_name}] failed: {message}")
        self.source_name = source_name
        self.original_exception = original_exception


class BaseSourceCollector(ABC):
    """Abstract base class for all source adapters."""

    def __init__(
        self,
        name: str,
        feed_url: str,
        base_url: str,
        config_metadata: Optional[Dict[str, Any]] = None,
        http_client: Optional[ResilientHttpClient] = None,
    ):
        self.name = name
        self.feed_url = feed_url
        self.base_url = base_url
        self.config_metadata = config_metadata or {}
        self.http_client = http_client or ResilientHttpClient()
        self.logger = setup_logger(f"collector.{self.name}")

    @abstractmethod
    def fetch_raw(self) -> Any:
        """Fetch raw data payload from the external source."""
        pass

    @abstractmethod
    def parse_and_normalize(self, raw_data: Any) -> List[NormalizedDocument]:
        """Convert raw source payload into standardized NormalizedDocument models."""
        pass

    def collect(self) -> List[NormalizedDocument]:
        """Orchestrate retrieval and normalization with performance measurement and logging."""
        start_time = time.perf_counter()
        self.logger.info(f"Starting ingestion from '{self.name}' ({self.feed_url})")

        try:
            raw_data = self.fetch_raw()
            documents = self.parse_and_normalize(raw_data)
            duration = time.perf_counter() - start_time
            self.logger.info(
                f"Successfully collected {len(documents)} documents from '{self.name}' in {duration:.2f}s"
            )
            return documents
        except Exception as exc:
            duration = time.perf_counter() - start_time
            self.logger.error(
                f"Failed collection from '{self.name}' after {duration:.2f}s: {exc}",
                exc_info=True,
            )
            raise CollectorError(
                source_name=self.name,
                message=str(exc),
                original_exception=exc,
            ) from exc
