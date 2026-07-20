"""Append-only JSONL audit log for remediation and webhook decisions."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def audit_path(cfg_path: Optional[str] = None) -> str:
    return cfg_path or os.getenv("AUTOSRE_AUDIT_LOG", "logs/autosre-audit.jsonl")


def write_event(event_type: str, payload: dict[str, Any], path: Optional[str] = None) -> str:
    """Append one audit event. Returns the path written."""
    dest = audit_path(path)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "event": event_type,
        **payload,
    }
    line = json.dumps(record, default=str)
    with _lock:
        with open(dest, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    logger.info("audit %s", event_type)
    return dest
