from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
import pytest

from teamarr_mcp.spec import load_vendored

Handler = Callable[[httpx2.Request], httpx2.Response]


@pytest.fixture(scope="session")
def vendored_spec() -> dict:
    return load_vendored()


@pytest.fixture
def make_client() -> Callable[[Handler], httpx2.AsyncClient]:
    def _make(handler: Handler) -> httpx2.AsyncClient:
        return httpx2.AsyncClient(
            base_url="http://teamarr.test", transport=httpx2.MockTransport(handler)
        )

    return _make


def json_response(status: int, payload) -> httpx2.Response:
    return httpx2.Response(status, json=payload)


def body_of(request: httpx2.Request) -> dict:
    return json.loads(request.content.decode() or "{}")
