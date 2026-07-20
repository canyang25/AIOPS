"""Tool definitions and thin dispatch over backend adapters + policy gate."""

from __future__ import annotations

import logging
import time
from typing import Optional

from autosre import audit
from autosre.approval import ApprovalGate
from autosre.backends import ansible as ansible_backend
from autosre.backends import logs as logs_backend
from autosre.backends import metrics as metrics_backend
from autosre.config import AutoSREConfig
from autosre.logging import log_extra
from autosre.metrics_self import METRICS
from autosre.policy import evaluate_remediation
from autosre.retry import retry_http

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "name": "query_metrics",
        "description": "Query time-series metrics for a service from Prometheus. "
        "Returns summary stats (min/max/avg/latest) over the recent window.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "The name of the service to query."},
                "metric": {"type": "string", "description": "The name of the metric to query."},
            },
            "required": ["service", "metric"],
        },
    },
    {
        "name": "search_logs",
        "description": "Search recent logs for a service in ELK, optionally filtered by level.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "level": {
                    "type": "string",
                    "enum": ["INFO", "WARN", "ERROR"],
                    "description": "optional level filter",
                },
            },
            "required": ["service"],
        },
    },
    {
        "name": "run_playbook",
        "description": "Execute an Ansible remediation playbook against the given hosts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "playbook": {"type": "string", "description": "The name of the playbook to run."},
                "hosts": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["playbook"],
        },
    },
    {
        "name": "list_playbooks",
        "description": (
            "List available Ansible remediation playbooks and their descriptions. "
            "Call this to discover what playbooks are available before running one."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


def _cfg(cfg: Optional[AutoSREConfig] = None) -> AutoSREConfig:
    return cfg or AutoSREConfig.from_env()


@retry_http
def _tool_query_metrics(service: str, metric: str, cfg: Optional[AutoSREConfig] = None) -> dict:
    return metrics_backend.query_metrics(service, metric, cfg=_cfg(cfg))


@retry_http
def _tool_search_logs(
    service: str, level: str = None, cfg: Optional[AutoSREConfig] = None
) -> dict:
    return logs_backend.search_logs(service, level, cfg=_cfg(cfg))


@retry_http
def _tool_run_playbook(
    playbook: str, hosts: list = None, cfg: Optional[AutoSREConfig] = None
) -> dict:
    return ansible_backend.run_playbook(playbook, hosts, cfg=_cfg(cfg))


@retry_http
def _tool_list_playbooks(cfg: Optional[AutoSREConfig] = None) -> dict:
    return ansible_backend.list_playbooks(cfg=_cfg(cfg))


TOOL_DISPATCH = {
    "query_metrics": _tool_query_metrics,
    "search_logs": _tool_search_logs,
    "run_playbook": _tool_run_playbook,
    "list_playbooks": _tool_list_playbooks,
}


def _dispatch(
    name: str,
    tool_input: dict,
    cfg: Optional[AutoSREConfig] = None,
    approval: Optional[ApprovalGate] = None,
) -> dict:
    """Dispatch a tool call through policy + approval gates for remediations."""
    start = time.monotonic()
    runtime_cfg = _cfg(cfg)
    try:
        if name not in TOOL_DISPATCH:
            raise KeyError(f"unknown tool: {name}")

        if name == "run_playbook":
            playbook = tool_input.get("playbook", "")
            hosts = tool_input.get("hosts") or ["localhost"]

            decision = evaluate_remediation(playbook, hosts, runtime_cfg)
            if not decision.allowed:
                METRICS.incr("remediations_blocked")
                audit.write_event(
                    "remediation_denied_policy",
                    {
                        "playbook": playbook,
                        "hosts": hosts,
                        "reason": decision.reason,
                        "blast_hosts": decision.blast_hosts,
                    },
                    path=runtime_cfg.audit_log_path,
                )
                return {
                    "error": f"Remediation denied by policy: {decision.reason}",
                    "denied": True,
                    "policy": decision.reason,
                }

            gate = approval or ApprovalGate(runtime_cfg)
            if not gate.request_approval(playbook, hosts, context=tool_input):
                METRICS.incr("remediations_blocked")
                audit.write_event(
                    "remediation_denied_operator",
                    {"playbook": playbook, "hosts": hosts},
                    path=runtime_cfg.audit_log_path,
                )
                return {"error": "Remediation denied by operator", "denied": True}

            METRICS.incr("remediations_allowed")
            audit.write_event(
                "remediation_allowed",
                {
                    "playbook": playbook,
                    "hosts": hosts,
                    "blast_hosts": decision.blast_hosts,
                },
                path=runtime_cfg.audit_log_path,
            )

        kwargs = dict(tool_input)
        kwargs["cfg"] = runtime_cfg
        result = TOOL_DISPATCH[name](**kwargs)
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            "tool ok",
            extra=log_extra(tool=name, duration_ms=duration_ms),
        )
        return result
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.warning(
            "tool error: %s",
            exc,
            extra=log_extra(tool=name, duration_ms=duration_ms),
        )
        return {"error": f"{type(exc).__name__}: {exc}"}
