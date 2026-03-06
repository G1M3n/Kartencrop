from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Optional

import requests


DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class HttpResult:
    url: str
    status_code: int
    content_type: str
    content: bytes

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


def create_session(user_agent: str = DEFAULT_BROWSER_UA) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    return session


def _retry_after_seconds(response: requests.Response | None) -> float | None:
    if response is None:
        return None
    raw_value = response.headers.get("Retry-After")
    if not raw_value:
        return None
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return None


def get_with_retries(
    session: requests.Session,
    url: str,
    *,
    params: Optional[dict[str, str]] = None,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 10.0,
    max_attempts: int = 3,
    backoff_seconds: float = 0.5,
) -> requests.Response | None:
    attempts = max(1, int(max_attempts))

    for attempt in range(attempts):
        response: requests.Response | None = None
        try:
            response = session.get(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException:
            if attempt >= attempts - 1:
                return None
        else:
            if response.status_code not in RETRYABLE_STATUS_CODES:
                return response
            if attempt >= attempts - 1:
                return response

        delay = _retry_after_seconds(response)
        if delay is None:
            delay = float(backoff_seconds) * (2 ** attempt)
        time.sleep(delay)

    return None


def warmup_session(session: requests.Session, url: str, timeout: float = 15.0) -> None:
    get_with_retries(session, url, timeout=timeout)


def request_bytes(
    url: str,
    session: Optional[requests.Session] = None,
    headers: Optional[dict[str, str]] = None,
    params: Optional[dict[str, str]] = None,
    timeout: float = 10.0,
    max_attempts: int = 3,
    backoff_seconds: float = 0.5,
) -> HttpResult:
    if session is None:
        session = create_session()

    resp = get_with_retries(
        session,
        url,
        params=params,
        headers=headers,
        timeout=timeout,
        max_attempts=max_attempts,
        backoff_seconds=backoff_seconds,
    )
    if resp is None:
        return HttpResult(
            url=url,
            status_code=0,
            content_type="",
            content=b"",
        )
    return HttpResult(
        url=url,
        status_code=resp.status_code,
        content_type=resp.headers.get("Content-Type", ""),
        content=resp.content,
    )
