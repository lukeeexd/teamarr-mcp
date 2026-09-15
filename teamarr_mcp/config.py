"""Environment-driven configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}
_TRANSPORTS = {"http", "stdio"}


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in _TRUE


@dataclass(frozen=True)
class Settings:
    url: str = "http://localhost:9195"
    api_key: str | None = None
    api_key_header: str = "X-API-Key"
    transport: str = "http"
    host: str = "0.0.0.0"
    port: int = 8000
    enable_destructive: bool = False
    read_only: bool = False
    openapi_path: str | None = None
    log_level: str = "INFO"
    exclude_paths: tuple[str, ...] = ()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        transport = e.get("TEAMARR_MCP_TRANSPORT", "http").strip().lower()
        if transport not in _TRANSPORTS:
            raise ValueError(
                f"TEAMARR_MCP_TRANSPORT must be one of {sorted(_TRANSPORTS)}, got {transport!r}"
            )
        return cls(
            url=e.get("TEAMARR_URL", "http://localhost:9195").strip().rstrip("/"),
            api_key=e.get("TEAMARR_API_KEY") or None,
            api_key_header=e.get("TEAMARR_API_KEY_HEADER", "X-API-Key").strip(),
            transport=transport,
            host=e.get("TEAMARR_MCP_HOST", "0.0.0.0").strip(),
            port=int(e.get("TEAMARR_MCP_PORT", "8000")),
            enable_destructive=_bool(e.get("TEAMARR_MCP_ENABLE_DESTRUCTIVE")),
            read_only=_bool(e.get("TEAMARR_MCP_READ_ONLY")),
            openapi_path=e.get("TEAMARR_OPENAPI_PATH") or None,
            log_level=e.get("TEAMARR_MCP_LOG_LEVEL", "INFO").strip().upper(),
            exclude_paths=tuple(
                s.strip() for s in e.get("TEAMARR_MCP_EXCLUDE_PATHS", "").split(",") if s.strip()
            ),
        )

    @property
    def headers(self) -> dict[str, str]:
        return {self.api_key_header: self.api_key} if self.api_key else {}
