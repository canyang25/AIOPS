"""Configuration loaded from environment variables."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

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
    playbook_allowlist: List[str] = field(default_factory=list)
    max_remediation_hosts: int = 5
    forbidden_host_substrings: List[str] = field(default_factory=list)
    audit_log_path: str = "logs/autosre-audit.jsonl"
    webhook_rate_limit_per_minute: int = 30
    require_webhook_token: bool = False

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

        allow_raw = _env("AUTOSRE_PLAYBOOK_ALLOWLIST", "")
        allowlist = [p.strip() for p in allow_raw.split(",") if p.strip()]

        forbid_raw = _env("AUTOSRE_FORBIDDEN_HOST_SUBSTRINGS", "")
        forbidden = [p.strip() for p in forbid_raw.split(",") if p.strip()]

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
            playbook_allowlist=allowlist,
            max_remediation_hosts=int(_env("AUTOSRE_MAX_REMEDIATION_HOSTS", "5") or "5"),
            forbidden_host_substrings=forbidden,
            audit_log_path=_env("AUTOSRE_AUDIT_LOG", "logs/autosre-audit.jsonl")
            or "logs/autosre-audit.jsonl",
            webhook_rate_limit_per_minute=int(
                _env("AUTOSRE_WEBHOOK_RATE_LIMIT_PER_MINUTE", "30") or "30"
            ),
            require_webhook_token=_env("AUTOSRE_REQUIRE_WEBHOOK_TOKEN", "").lower()
            in {"1", "true", "yes"},
        )

    def request_headers(self) -> Dict[str, str]:
        """Outbound HTTP headers for tool calls."""
        headers = dict(self.http_headers)
        if self.http_authorization:
            headers["Authorization"] = self.http_authorization
        return headers

    def validate(self) -> Tuple[bool, List[str]]:
        """Return (ok, errors) for readiness checks."""
        errors: List[str] = []
        if self.backend_mode not in {"mock", "real"}:
            errors.append(f"invalid AUTOSRE_BACKEND_MODE={self.backend_mode!r}")
        if self.approval_mode not in {"auto", "prompt", "webhook"}:
            errors.append(f"invalid AUTOSRE_APPROVAL_MODE={self.approval_mode!r}")
        if self.approval_mode == "webhook" and not self.approval_webhook_url:
            errors.append("AUTOSRE_APPROVAL_WEBHOOK_URL required when approval_mode=webhook")
        if self.backend_mode == "real" and not self.http_authorization:
            errors.append("AUTOSRE_HTTP_AUTHORIZATION recommended/required for backend_mode=real")
        if self.require_webhook_token and not self.webhook_token:
            errors.append("AUTOSRE_WEBHOOK_TOKEN required when AUTOSRE_REQUIRE_WEBHOOK_TOKEN=true")
        if self.max_remediation_hosts < 1:
            errors.append("AUTOSRE_MAX_REMEDIATION_HOSTS must be >= 1")
        if self.timeout < 1:
            errors.append("AUTOSRE_TIMEOUT must be >= 1")
        return (len(errors) == 0, errors)


load_env()
config = AutoSREConfig.from_env()
