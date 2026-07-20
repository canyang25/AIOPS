"""Tool definitions and HTTP wrappers for mock / real observability backends."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests

from autosre.approval import ApprovalGate
from autosre.config import AutoSREConfig
from autosre.logging import log_extra
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


def _headers(cfg: AutoSREConfig) -> dict[str, str]:
    return cfg.request_headers()


def _summarize_values(service: str, metric: str, nums: list[float]) -> dict:
    return {
        "service": service,
        "metric": metric,
        "points": len(nums),
        "min": round(min(nums), 2),
        "max": round(max(nums), 2),
        "avg": round(sum(nums) / len(nums), 2),
        "latest": round(nums[-1], 2),
        "raw_values": nums,
    }


@retry_http
def _tool_query_metrics(service: str, metric: str, cfg: Optional[AutoSREConfig] = None) -> dict:
    c = _cfg(cfg)
    headers = _headers(c)

    if c.backend_mode == "real":
        # Real Prometheus: PromQL query_range (query/start/end/step).
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=15)
        query = c.prometheus_query_template.format(metric=metric, service=service)
        resp = requests.get(
            f"{c.prometheus_url}/api/v1/query_range",
            params={
                "query": query,
                "start": start.timestamp(),
                "end": end.timestamp(),
                "step": 60,
            },
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()["data"]["result"]
        if not result:
            raise ValueError(f"no series for query={query!r}")
        values = result[0]["values"]
        nums = [float(v) for _, v in values]
        return _summarize_values(service, metric, nums)

    # Mock contract: service + metric query params.
    resp = requests.get(
        f"{c.prometheus_url}/api/v1/query_range",
        params={"service": service, "metric": metric},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    values = resp.json()["data"]["result"][0]["values"]
    nums = [float(v) for _, v in values]
    return _summarize_values(service, metric, nums)


@retry_http
def _tool_search_logs(
    service: str, level: str = None, cfg: Optional[AutoSREConfig] = None
) -> dict:
    c = _cfg(cfg)
    headers = _headers(c)

    if c.backend_mode == "real":
        # Elasticsearch Query DSL against a configured index.
        must: list[dict[str, Any]] = [{"term": {"service.keyword": service}}]
        if level:
            must.append({"term": {"level.keyword": level}})
        body = {"query": {"bool": {"must": must}}, "size": 20}
        resp = requests.post(
            f"{c.elk_url}/{c.elk_index}/_search",
            json=body,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        hits = resp.json()["hits"]
        total = hits["total"]["value"] if isinstance(hits["total"], dict) else hits["total"]
        return {
            "service": service,
            "level": level,
            "total": total,
            "logs": [h["_source"] for h in hits["hits"]],
        }

    query: dict[str, Any] = {"service": service}
    if level:
        query["level"] = level
    resp = requests.post(
        f"{c.elk_url}/_search",
        json={"query": query},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    hits = resp.json()["hits"]
    return {
        "service": service,
        "level": level,
        "total": hits["total"]["value"],
        "logs": [h["_source"] for h in hits["hits"]],
    }


@retry_http
def _tool_run_playbook(
    playbook: str, hosts: list = None, cfg: Optional[AutoSREConfig] = None
) -> dict:
    c = _cfg(cfg)
    headers = _headers(c)
    hosts = hosts or ["localhost"]

    if c.backend_mode == "real":
        # AWX / Automation Controller job template launch.
        template_id = c.awx_job_template_map.get(playbook)
        if not template_id:
            raise KeyError(
                f"no AWX job template mapped for playbook {playbook!r}; "
                "set AWX_JOB_TEMPLATE_MAP_JSON"
            )
        resp = requests.post(
            f"{c.ansible_url}/api/v2/job_templates/{template_id}/launch/",
            json={"limit": ",".join(hosts)},
            headers={**headers, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        return {
            "status": "success" if resp.status_code in (200, 201) else "unknown",
            "playbook": playbook,
            "job": body.get("job") or body.get("id"),
            "raw": body,
        }

    resp = requests.post(
        f"{c.ansible_url}/api/v1/execute",
        json={"playbook": playbook, "hosts": hosts},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


@retry_http
def _tool_list_playbooks(cfg: Optional[AutoSREConfig] = None) -> dict:
    c = _cfg(cfg)
    headers = _headers(c)

    if c.backend_mode == "real":
        resp = requests.get(
            f"{c.ansible_url}/api/v2/job_templates/",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        playbooks = {
            item.get("name", str(item.get("id"))): {
                "description": item.get("description", ""),
                "id": item.get("id"),
            }
            for item in results
        }
        return {"playbooks": playbooks}

    resp = requests.get(
        f"{c.ansible_url}/api/v1/playbooks",
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


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
    """Dispatch a tool call, gating run_playbook behind the approval gate."""
    start = time.monotonic()
    runtime_cfg = _cfg(cfg)
    try:
        if name not in TOOL_DISPATCH:
            raise KeyError(f"unknown tool: {name}")

        if name == "run_playbook":
            gate = approval or ApprovalGate(runtime_cfg)
            playbook = tool_input.get("playbook", "")
            hosts = tool_input.get("hosts") or ["localhost"]
            if not gate.request_approval(playbook, hosts, context=tool_input):
                return {"error": "Remediation denied by operator", "denied": True}

        kwargs = dict(tool_input)
        kwargs["cfg"] = runtime_cfg
        result = TOOL_DISPATCH[name](**kwargs)
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            "tool ok",
            extra=log_extra(tool=name, duration_ms=duration_ms),
        )
        return result
    except Exception as exc:  # surface tool failures to the model instead of crashing
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.warning(
            "tool error: %s",
            exc,
            extra=log_extra(tool=name, duration_ms=duration_ms),
        )
        return {"error": f"{type(exc).__name__}: {exc}"}
