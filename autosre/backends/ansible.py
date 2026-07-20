"""Ansible mock / AWX remediation backends."""

from __future__ import annotations

from typing import Optional

from autosre.backends import http as http_client
from autosre.config import AutoSREConfig


def run_playbook(
    playbook: str, hosts: list = None, cfg: Optional[AutoSREConfig] = None
) -> dict:
    c = cfg or AutoSREConfig.from_env()
    hosts = hosts or ["localhost"]

    if c.backend_mode == "real":
        template_id = c.awx_job_template_map.get(playbook)
        if not template_id:
            raise KeyError(
                f"no AWX job template mapped for playbook {playbook!r}; "
                "set AWX_JOB_TEMPLATE_MAP_JSON"
            )
        status, body = http_client.post_json(
            f"{c.ansible_url}/api/v2/job_templates/{template_id}/launch/",
            cfg=c,
            payload={"limit": ",".join(hosts)},
            timeout=30,
        )
        return {
            "status": "success" if status in (200, 201) else "unknown",
            "playbook": playbook,
            "job": body.get("job") or body.get("id"),
            "raw": body,
        }

    _status, body = http_client.post_json(
        f"{c.ansible_url}/api/v1/execute",
        cfg=c,
        payload={"playbook": playbook, "hosts": hosts},
    )
    return body


def list_playbooks(cfg: Optional[AutoSREConfig] = None) -> dict:
    c = cfg or AutoSREConfig.from_env()

    if c.backend_mode == "real":
        data = http_client.get_json(
            f"{c.ansible_url}/api/v2/job_templates/",
            cfg=c,
        )
        results = data.get("results", [])
        playbooks = {
            item.get("name", str(item.get("id"))): {
                "description": item.get("description", ""),
                "id": item.get("id"),
            }
            for item in results
        }
        return {"playbooks": playbooks}

    return http_client.get_json(f"{c.ansible_url}/api/v1/playbooks", cfg=c)
