from typing import List, Any, Dict, Optional
from backend.app.collectors.base import BaseSourceCollector
from backend.app.schemas.document import NormalizedDocument
from backend.app.processors.normalizer import build_normalized_document
from backend.app.utils.time import utc_now, parse_datetime_utc


class APICollector(BaseSourceCollector):
    """Generic collector adapter for structured JSON REST APIs."""

    def fetch_raw(self) -> Any:
        """Fetch JSON payload from the API endpoint."""
        custom_headers = {"Accept": "application/json, */*"}
        custom_headers.update(self.config_metadata.get("headers", {}))
        params = self.config_metadata.get("params") or None
        response = self.http_client.get(self.feed_url, headers=custom_headers, params=params)
        return response.json()

    def parse_and_normalize(self, raw_data: Any) -> List[NormalizedDocument]:
        """Transform JSON response into normalized documents using field mappings."""
        field_mapping = self.config_metadata.get("field_mapping", {})
        items_path = self.config_metadata.get("items_path")

        # Navigate nested items path if specified (supports dict keys and list indices)
        items = raw_data
        if items_path:
            for key in items_path.split("."):
                if isinstance(items, dict):
                    items = items.get(key, [])
                elif isinstance(items, list) and key.isdigit():
                    idx = int(key)
                    items = items[idx] if 0 <= idx < len(items) else []
                else:
                    break

        if not isinstance(items, list):
            if isinstance(items, dict):
                if all(isinstance(v, dict) for v in items.values()) and items:
                    items = [{"key": k, "id": k, **v} for k, v in items.items()]
                else:
                    items = [items]
            else:
                return []

        title_key = field_mapping.get("title", "title")
        url_key = field_mapping.get("url", "url")
        id_key = field_mapping.get("id", "id")
        desc_key = field_mapping.get("description", "description")
        content_key = field_mapping.get("content", "content")
        author_key = field_mapping.get("author", "author")
        date_key = field_mapping.get("published_at", "published_at")
        lang_key = field_mapping.get("language", "language")

        normalized_docs: List[NormalizedDocument] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            try:
                title = item.get(title_key, "")
                url = item.get(url_key, "")
                if not url and not title:
                    continue

                external_id = item.get(id_key)
                description = item.get(desc_key)
                content = item.get(content_key) or description
                author = item.get(author_key)
                language = item.get(lang_key, "en")

                raw_date = item.get(date_key)
                if raw_date:
                    try:
                        published_at = parse_datetime_utc(raw_date)
                    except Exception:
                        published_at = utc_now()
                else:
                    published_at = utc_now()

                doc = build_normalized_document(
                    source_name=self.name,
                    title=str(title),
                    url=str(url),
                    published_at=published_at,
                    external_id=str(external_id) if external_id is not None else None,
                    description=str(description) if description is not None else None,
                    content=str(content) if content is not None else None,
                    author=str(author) if author is not None else None,
                    language=str(language),
                    raw_metadata={"raw_item": item},
                )
                normalized_docs.append(doc)
            except Exception as item_exc:
                self.logger.warning(f"Failed to normalize JSON item in {self.name}: {item_exc}")
                continue

        return normalized_docs
