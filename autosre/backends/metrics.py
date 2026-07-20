"""Prometheus / mock metrics backends."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from autosre.backends import http as http_client
from autosre.config import AutoSREConfig


def _summarize(service: str, metric: str, nums: list[float]) -> dict:
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


def query_metrics(
    service: str, metric: str, cfg: Optional[AutoSREConfig] = None
) -> dict:
    c = cfg or AutoSREConfig.from_env()
    if c.backend_mode == "real":
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=15)
        query = c.prometheus_query_template.format(metric=metric, service=service)
        data = http_client.get_json(
            f"{c.prometheus_url}/api/v1/query_range",
            cfg=c,
            params={
                "query": query,
                "start": start.timestamp(),
                "end": end.timestamp(),
                "step": 60,
            },
        )
        result = data["data"]["result"]
        if not result:
            raise ValueError(f"no series for query={query!r}")
        values = result[0]["values"]
        nums = [float(v) for _, v in values]
        return _summarize(service, metric, nums)

    data = http_client.get_json(
        f"{c.prometheus_url}/api/v1/query_range",
        cfg=c,
        params={"service": service, "metric": metric},
    )
    values = data["data"]["result"][0]["values"]
    nums = [float(v) for _, v in values]
    return _summarize(service, metric, nums)
