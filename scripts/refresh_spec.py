"""Refresh teamarr_mcp/specs/openapi.json from a running Teamarr.

Usage: uv run python scripts/refresh_spec.py http://192.168.1.63:9195
"""

import json
import sys
from pathlib import Path

import httpx2

url = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9195").rstrip("/")
spec = httpx2.get(f"{url}/openapi.json", timeout=30).raise_for_status().json()
out = Path(__file__).resolve().parent.parent / "teamarr_mcp" / "specs" / "openapi.json"
out.write_text(json.dumps(spec, indent=1) + "\n", encoding="utf-8")
METHODS = ("get", "post", "put", "patch", "delete")
ops = sum(1 for p in spec["paths"].values() for m in p if m in METHODS)
print(f"wrote {out} (Teamarr {spec['info'].get('version')}, {len(spec['paths'])} paths, {ops} ops)")
