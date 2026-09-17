from typing import Any, Optional, Dict
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from backend.app.config.settings import get_settings
from backend.app.utils.logger import setup_logger

logger = setup_logger("http_client")


class HttpClientError(Exception):
    """Base exception for HTTP client operations."""
    pass


class HttpTimeoutError(HttpClientError):
    """Raised when an HTTP request times out."""
    pass


class HttpStatusError(HttpClientError):
    """Raised when an HTTP response returns an error status code."""
    def __init__(self, status_code: int, message: str, url: str):
        super().__init__(f"HTTP {status_code} for {url}: {message}")
        self.status_code = status_code
        self.url = url


class ResilientHttpClient:
    """HTTP client with configurable retries, exponential backoff, timeouts, and headers."""

    def __init__(
        self,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        user_agent: Optional[str] = None,
    ):
        settings = get_settings()
        self.timeout_seconds = timeout_seconds or settings.REQUEST_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.MAX_RETRIES
        self.backoff_factor = backoff_factor or settings.BACKOFF_FACTOR
        self.user_agent = user_agent or settings.DEFAULT_USER_AGENT

    def _get_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/xml, application/rss+xml, application/atom+xml, application/json, text/xml, text/html;q=0.9, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "no-cache",
        }
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Perform a synchronous HTTP GET request with retries and exponential backoff."""
        request_headers = self._get_headers(headers)

        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=self.backoff_factor, min=1, max=10),
            retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
            before_sleep=before_sleep_log(logger, getattr(logger, "level", 20)),
            reraise=True,
        )
        def _execute() -> httpx.Response:
            try:
                with httpx.Client(
                    timeout=httpx.Timeout(self.timeout_seconds),
                    follow_redirects=True,
                ) as client:
                    response = client.get(url, params=params if params else None, headers=request_headers)
                    response.raise_for_status()
                    return response
            except httpx.TimeoutException as exc:
                logger.warning(f"Timeout fetching {url}: {exc}")
                raise
            except httpx.HTTPStatusError as exc:
                logger.warning(f"HTTP error {exc.response.status_code} fetching {url}")
                raise HttpStatusError(
                    status_code=exc.response.status_code,
                    message=exc.response.text[:200],
                    url=url,
                ) from exc
            except httpx.RequestError as exc:
                logger.warning(f"Request error fetching {url}: {exc}")
                raise

        try:
            return _execute()
        except httpx.TimeoutException as exc:
            raise HttpTimeoutError(f"Request to {url} timed out after {self.timeout_seconds}s") from exc
        except httpx.RequestError as exc:
            raise HttpClientError(f"Failed to connect to {url}: {exc}") from exc
