"""Policy / blast-radius gate tests — allowlist from fixtures."""

import json
from pathlib import Path

from autosre.config import AutoSREConfig
from autosre.policy import allowed_playbooks, evaluate_remediation
from autosre.tools import _dispatch


def _fixture_playbooks():
    path = Path(__file__).resolve().parents[1] / "fixtures" / "playbooks.json"
    return sorted(json.loads(path.read_text(encoding="utf-8")).keys())


def test_allowlist_defaults_to_fixtures():
    names = allowed_playbooks(AutoSREConfig())
    assert names == _fixture_playbooks()


def test_policy_blocks_unknown_playbook():
    cfg = AutoSREConfig(playbook_allowlist=_fixture_playbooks()[:1])
    decision = evaluate_remediation("not-a-real-playbook.yml", ["localhost"], cfg)
    assert decision.allowed is False
    assert "allowlist" in decision.reason


def test_policy_blocks_oversized_blast_radius():
    playbook = _fixture_playbooks()[0]
    cfg = AutoSREConfig(max_remediation_hosts=1, playbook_allowlist=_fixture_playbooks())
    decision = evaluate_remediation(playbook, ["h1", "h2"], cfg)
    assert decision.allowed is False
    assert "blast radius" in decision.reason


def test_policy_blocks_forbidden_host():
    playbook = _fixture_playbooks()[0]
    cfg = AutoSREConfig(
        playbook_allowlist=_fixture_playbooks(),
        forbidden_host_substrings=["prod-db"],
    )
    decision = evaluate_remediation(playbook, ["prod-db-1"], cfg)
    assert decision.allowed is False
    assert "forbidden" in decision.reason


def test_dispatch_policy_deny(tmp_path):
    cfg = AutoSREConfig(
        playbook_allowlist=_fixture_playbooks(),
        max_remediation_hosts=1,
        audit_log_path=str(tmp_path / "audit.jsonl"),
    )
    result = _dispatch(
        "run_playbook",
        {"playbook": _fixture_playbooks()[0], "hosts": ["a", "b", "c"]},
        cfg=cfg,
    )
    assert result.get("denied") is True
    assert "policy" in result.get("error", "").lower() or result.get("policy")
    assert (tmp_path / "audit.jsonl").is_file()
