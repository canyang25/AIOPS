"""ELK / Elasticsearch log backends."""

from __future__ import annotations

from typing import Any, Optional

from autosre.backends import http as http_client
from autosre.config import AutoSREConfig


def search_logs(
    service: str, level: str = None, cfg: Optional[AutoSREConfig] = None
) -> dict:
    c = cfg or AutoSREConfig.from_env()

    if c.backend_mode == "real":
        must: list[dict[str, Any]] = [{"term": {"service.keyword": service}}]
        if level:
            must.append({"term": {"level.keyword": level}})
        _status, data = http_client.post_json(
            f"{c.elk_url}/{c.elk_index}/_search",
            cfg=c,
            payload={"query": {"bool": {"must": must}}, "size": 20},
        )
        hits = data["hits"]
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
    _status, data = http_client.post_json(
        f"{c.elk_url}/_search",
        cfg=c,
        payload={"query": query},
    )
    hits = data["hits"]
    return {
        "service": service,
        "level": level,
        "total": hits["total"]["value"],
        "logs": [h["_source"] for h in hits["hits"]],
    }
