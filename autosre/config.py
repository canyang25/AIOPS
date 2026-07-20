"""Configuration loaded from environment variables."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List

from autosre.bootstrap import load_env


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


@dataclass
class AutoSREConfig:
    """Runtime configuration for AutoSRE."""

    prometheus_url: str = "http://localhost:9091"
    elk_url: str = "http://localhost:9093"
    ansible_url: str = "http://localhost:9092"
    approval_mode: str = "auto"  # auto | prompt | webhook
    approval_webhook_url: str = ""
    timeout: int = 300
    fallback_chain: List[str] = field(default_factory=list)
    rollback_playbook: str = ""
    port: int = 8080
    db_path: str = "autosre.db"
    max_iterations: int = 12
    backend_mode: str = "mock"  # mock | real
    http_authorization: str = ""
    http_headers: Dict[str, str] = field(default_factory=dict)
    prometheus_query_template: str = '{metric}{{service="{service}"}}'
    elk_index: str = "logs-*"
    awx_job_template_map: Dict[str, str] = field(default_factory=dict)
    webhook_token: str = ""

    @classmethod
    def from_env(cls) -> "AutoSREConfig":
        load_env()
        chain_raw = _env("LLM_FALLBACK_CHAIN", "")
        chain = [p.strip().lower() for p in chain_raw.split(",") if p.strip()]

        headers: Dict[str, str] = {}
        headers_raw = _env("AUTOSRE_HTTP_HEADERS_JSON", "")
        if headers_raw:
            try:
                parsed = json.loads(headers_raw)
                if isinstance(parsed, dict):
                    headers = {str(k): str(v) for k, v in parsed.items()}
            except json.JSONDecodeError:
                pass

        awx_map: Dict[str, str] = {}
        awx_raw = _env("AWX_JOB_TEMPLATE_MAP_JSON", "")
        if awx_raw:
            try:
                parsed = json.loads(awx_raw)
                if isinstance(parsed, dict):
                    awx_map = {str(k): str(v) for k, v in parsed.items()}
            except json.JSONDecodeError:
                pass

        return cls(
            prometheus_url=_env("PROMETHEUS_URL", "http://localhost:9091").rstrip("/"),
            elk_url=_env("ELK_URL", "http://localhost:9093").rstrip("/"),
            ansible_url=_env("ANSIBLE_URL", "http://localhost:9092").rstrip("/"),
            approval_mode=_env("AUTOSRE_APPROVAL_MODE", "auto").lower() or "auto",
            approval_webhook_url=_env("AUTOSRE_APPROVAL_WEBHOOK_URL", ""),
            timeout=int(_env("AUTOSRE_TIMEOUT", "300") or "300"),
            fallback_chain=chain,
            rollback_playbook=_env("AUTOSRE_ROLLBACK_PLAYBOOK", ""),
            port=int(_env("AUTOSRE_PORT", "8080") or "8080"),
            db_path=_env("AUTOSRE_DB_PATH", "autosre.db") or "autosre.db",
            max_iterations=int(_env("AUTOSRE_MAX_ITERATIONS", "12") or "12"),
            backend_mode=(_env("AUTOSRE_BACKEND_MODE", "mock") or "mock").lower(),
            http_authorization=_env("AUTOSRE_HTTP_AUTHORIZATION", ""),
            http_headers=headers,
            prometheus_query_template=_env(
                "PROMETHEUS_QUERY_TEMPLATE", '{metric}{{service="{service}"}}'
            )
            or '{metric}{{service="{service}"}}',
            elk_index=_env("ELK_INDEX", "logs-*") or "logs-*",
            awx_job_template_map=awx_map,
            webhook_token=_env("AUTOSRE_WEBHOOK_TOKEN", ""),
        )

    def request_headers(self) -> Dict[str, str]:
        """Outbound HTTP headers for tool calls."""
        headers = dict(self.http_headers)
        if self.http_authorization:
            headers["Authorization"] = self.http_authorization
        return headers


# Prefer AutoSREConfig.from_env() at call sites; this is a convenience snapshot.
load_env()
config = AutoSREConfig.from_env()
