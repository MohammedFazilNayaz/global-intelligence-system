from datetime import datetime, timezone
import time
from typing import List, Any, Dict, Optional
import feedparser
from backend.app.collectors.base import BaseSourceCollector
from backend.app.schemas.document import NormalizedDocument
from backend.app.processors.normalizer import build_normalized_document
from backend.app.utils.time import parse_datetime_utc, utc_now


class RSSCollector(BaseSourceCollector):
    """Collector adapter for RSS and Atom syndication feeds."""

    def fetch_raw(self) -> str:
        """Fetch raw XML content using resilient HTTP client."""
        custom_headers = self.config_metadata.get("headers", {})
        response = self.http_client.get(self.feed_url, headers=custom_headers)
        return response.text

    def parse_and_normalize(self, raw_data: str) -> List[NormalizedDocument]:
        """Parse RSS/Atom XML text and convert entries to NormalizedDocument models."""
        parsed = feedparser.parse(raw_data)
        
        # Check if feed has fatal syntax errors and no entries
        if getattr(parsed, "bozo", False) and not parsed.entries:
            bozo_exc = getattr(parsed, "bozo_exception", "Unknown XML parse error")
            raise ValueError(f"Malformed RSS feed for {self.name}: {bozo_exc}")

        feed_meta = parsed.get("feed", {})
        feed_language = feed_meta.get("language", "en")

        normalized_docs: List[NormalizedDocument] = []

        for entry in parsed.entries:
            try:
                title = entry.get("title", "")
                url = entry.get("link", "")
                if not url and not title:
                    self.logger.warning(f"Skipping empty RSS entry in {self.name}")
                    continue

                external_id = entry.get("id") or entry.get("guid") or url
                description = entry.get("summary") or entry.get("description")
                
                # Extract main content body if available
                content = None
                content_list = entry.get("content", [])
                if content_list and isinstance(content_list, list):
                    content = content_list[0].get("value")
                if not content:
                    content = description

                author = entry.get("author") or entry.get("dc_creator")
                
                # Extract publication timestamp
                published_at = None
                if entry.get("published_parsed"):
                    published_at = datetime.fromtimestamp(
                        time.mktime(entry["published_parsed"]), tz=timezone.utc
                    )
                elif entry.get("updated_parsed"):
                    published_at = datetime.fromtimestamp(
                        time.mktime(entry["updated_parsed"]), tz=timezone.utc
                    )
                elif entry.get("published"):
                    published_at = parse_datetime_utc(entry["published"])
                elif entry.get("updated"):
                    published_at = parse_datetime_utc(entry["updated"])
                else:
                    published_at = utc_now()

                # Raw metadata preservation
                raw_metadata = {
                    "feed_title": feed_meta.get("title"),
                    "tags": [tag.get("term") for tag in entry.get("tags", []) if tag.get("term")],
                    "entry_keys": list(entry.keys()),
                }

                doc = build_normalized_document(
                    source_name=self.name,
                    title=title,
                    url=url,
                    published_at=published_at,
                    external_id=str(external_id),
                    description=description,
                    content=content,
                    author=author,
                    language=feed_language,
                    raw_metadata=raw_metadata,
                )
                normalized_docs.append(doc)
            except Exception as item_exc:
                self.logger.warning(
                    f"Error normalizing entry in source '{self.name}': {item_exc}"
                )
                continue

        return normalized_docs
