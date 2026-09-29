from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API_HOST = "127.0.0.1"
API_PORT = 8765
HEALTH_URL = f"http://{API_HOST}:{API_PORT}/health"


def resource_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    return Path(bundle_root) if bundle_root else Path(__file__).resolve().parents[2]


def find_ccx(root: Path | None = None) -> Path | None:
    search_root = root or resource_root()
    matches = sorted(search_root.rglob("*.ccx"))
    return matches[0] if matches else None


def startup_command(executable: Path | None = None) -> str:
    launcher = os.getenv("CAPTIONGUARD_LAUNCHER")
    target = executable or (Path(launcher) if launcher else Path(sys.executable))
    return f'"{target}" --minimized'


def read_health(timeout: float = 0.8) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
            return payload if payload.get("service") == "captionguard-cn" else None
    except (OSError, ValueError, urllib.error.URLError):
        return None
