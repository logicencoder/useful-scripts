"""Tiny HTTP helpers for operator smoke scripts."""

from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple


def tcp_open(host: str, port: int, timeout: float = 2.0) -> Tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "open"
    except OSError as exc:
        return False, str(exc)


def get_json(
    url: str,
    timeout: float = 10.0,
    headers: Optional[Dict[str, str]] = None,
    method: str = "GET",
    body: Optional[bytes] = None,
) -> Tuple[Optional[Dict[str, Any]], int, str]:
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = resp.getcode()
            if not raw.strip():
                return {}, code, ""
            return json.loads(raw), code, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            data = None
        return data, exc.code, raw
    except Exception as exc:
        return None, 0, str(exc)


def print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def die(message: str, code: int = 1) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(code)
