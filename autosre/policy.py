"""Remediation policy / blast-radius gate.

Production autonomous remediation requires an explicit bound on what an agent
may touch before execution. This module is a minimal, replicable gate:

- playbook must be on the allowlist (from fixtures or env)
- host count must be <= max_hosts
- optional forbidden host substrings

Deny results are structured so callers can audit and persist ``denied``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from autosre.config import AutoSREConfig

logger = logging.getLogger(__name__)


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    blast_hosts: int = 0
    playbook: str = ""


def _fixture_playbooks() -> List[str]:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "playbooks.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return sorted(data.keys())
    except (OSError, json.JSONDecodeError):
        return []


def allowed_playbooks(cfg: Optional[AutoSREConfig] = None) -> List[str]:
    """Return the playbook allowlist (env override or fixtures)."""
    c = cfg or AutoSREConfig.from_env()
    if c.playbook_allowlist:
        return list(c.playbook_allowlist)
    return _fixture_playbooks()


def evaluate_remediation(
    playbook: str,
    hosts: Sequence[str],
    cfg: Optional[AutoSREConfig] = None,
) -> PolicyDecision:
    """Decide whether a remediation may proceed."""
    c = cfg or AutoSREConfig.from_env()
    hosts = list(hosts or ["localhost"])
    blast = len(hosts)

    allow = allowed_playbooks(c)
    if allow and playbook not in allow:
        return PolicyDecision(
            allowed=False,
            reason=f"playbook {playbook!r} not on allowlist",
            blast_hosts=blast,
            playbook=playbook,
        )

    if blast > c.max_remediation_hosts:
        return PolicyDecision(
            allowed=False,
            reason=(
                f"blast radius {blast} hosts exceeds max_remediation_hosts="
                f"{c.max_remediation_hosts}"
            ),
            blast_hosts=blast,
            playbook=playbook,
        )

    for host in hosts:
        for needle in c.forbidden_host_substrings:
            if needle and needle.lower() in host.lower():
                return PolicyDecision(
                    allowed=False,
                    reason=f"host {host!r} matches forbidden pattern {needle!r}",
                    blast_hosts=blast,
                    playbook=playbook,
                )

    return PolicyDecision(
        allowed=True,
        reason="ok",
        blast_hosts=blast,
        playbook=playbook,
    )
