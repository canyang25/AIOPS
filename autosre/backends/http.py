"""Shared HTTP helpers for backend adapters."""

from __future__ import annotations

from typing import Optional

import requests

from autosre.config import AutoSREConfig


def headers_for(cfg: AutoSREConfig) -> dict[str, str]:
    return cfg.request_headers()


def get_json(
    url: str,
    *,
    cfg: AutoSREConfig,
    params: Optional[dict] = None,
    timeout: int = 15,
) -> dict:
    resp = requests.get(url, params=params, headers=headers_for(cfg), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def post_json(
    url: str,
    *,
    cfg: AutoSREConfig,
    payload: Optional[dict] = None,
    timeout: int = 15,
) -> tuple[int, dict]:
    hdrs = {**headers_for(cfg), "Content-Type": "application/json"}
    resp = requests.post(url, json=payload or {}, headers=hdrs, timeout=timeout)
    resp.raise_for_status()
    body = resp.json() if resp.content else {}
    return resp.status_code, body
