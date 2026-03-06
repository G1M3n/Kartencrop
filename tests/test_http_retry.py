from __future__ import annotations

from dataclasses import dataclass

import requests

from kartencrop.http import HttpResult, get_with_retries, request_bytes


@dataclass
class FakeResponse:
    status_code: int
    headers: dict[str, str]
    content: bytes = b""


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_get_with_retries_retries_retryable_status(monkeypatch) -> None:
    monkeypatch.setattr("kartencrop.http.time.sleep", lambda *_args, **_kwargs: None)
    session = FakeSession(
        [
            FakeResponse(status_code=503, headers={}),
            FakeResponse(status_code=200, headers={"Content-Type": "image/png"}, content=b"ok"),
        ]
    )

    response = get_with_retries(session, "https://example.test/tile.png", max_attempts=3, backoff_seconds=0)

    assert response is not None
    assert response.status_code == 200
    assert session.calls == 2


def test_get_with_retries_retries_request_exception(monkeypatch) -> None:
    monkeypatch.setattr("kartencrop.http.time.sleep", lambda *_args, **_kwargs: None)
    session = FakeSession(
        [
            requests.RequestException("boom"),
            FakeResponse(status_code=200, headers={"Content-Type": "application/json"}, content=b"{}"),
        ]
    )

    response = get_with_retries(session, "https://example.test/data.json", max_attempts=3, backoff_seconds=0)

    assert response is not None
    assert response.status_code == 200
    assert session.calls == 2


def test_request_bytes_returns_empty_result_when_all_attempts_fail(monkeypatch) -> None:
    monkeypatch.setattr("kartencrop.http.time.sleep", lambda *_args, **_kwargs: None)
    session = FakeSession([requests.RequestException("boom"), requests.RequestException("boom")])

    result = request_bytes(
        "https://example.test/data.json",
        session=session,
        max_attempts=2,
        backoff_seconds=0,
    )

    assert isinstance(result, HttpResult)
    assert result.status_code == 0
    assert result.content == b""
