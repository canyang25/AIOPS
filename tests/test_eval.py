"""Tests for eval keyword scoring helpers — driven by SCENARIOS catalog."""

from scenarios import SCENARIOS
from eval import _keywords_present, evaluate_scenario, print_summary


def _named(*preferred: str) -> str:
    for name in preferred:
        if name in SCENARIOS:
            return name
    return sorted(SCENARIOS.keys())[0]


def test_keywords_present_from_catalog_root_cause():
    name = _named("db")
    phrase = SCENARIOS[name]["expected_root_cause"]
    assert _keywords_present(phrase, phrase)


def test_keywords_present_missing_bigram():
    name = _named("db")
    phrase = SCENARIOS[name]["expected_root_cause"]
    # Scramble word order so consecutive bigrams fail.
    words = [w for w in phrase.lower().split() if len(w) > 2]
    scrambled = " ".join(reversed(words))
    if len(words) >= 2:
        assert not _keywords_present(scrambled, phrase)


def test_keywords_present_empty_phrase():
    assert _keywords_present("anything", "a to")


def test_partial_score_with_mock_report(tmp_path, monkeypatch):
    name = _named("db")
    scenario = SCENARIOS[name]
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / f"incident-{scenario['alert_id']}-20250101T000000Z.md").write_text(
        f"# Report\n\n## Root Cause\n{scenario['expected_root_cause']}\n\n"
        "## Remediation\nunrelated fix\n"
    )

    import eval as eval_mod

    monkeypatch.setattr(eval_mod, "REPORTS_DIR", str(reports))
    monkeypatch.setattr(eval_mod, "run_agent", lambda _name: 0)

    result = evaluate_scenario(name, simulate=False)
    assert result["root_cause_match"] is True
    assert result["remediation_match"] is False
    assert result["score"] == 0.5
    assert result["passed"] is False


def test_full_score_with_mock_report(tmp_path, monkeypatch):
    name = _named("disk")
    scenario = SCENARIOS[name]
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / f"incident-{scenario['alert_id']}-20250101T000000Z.md").write_text(
        f"{scenario['expected_root_cause']}. Ran {scenario['expected_remediation']}."
    )

    import eval as eval_mod

    monkeypatch.setattr(eval_mod, "REPORTS_DIR", str(reports))
    monkeypatch.setattr(eval_mod, "run_agent", lambda _name: 0)

    result = evaluate_scenario(name, simulate=False)
    assert result["score"] == 1.0
    assert result["passed"] is True


def test_simulate_mode():
    name = _named("network")
    result = evaluate_scenario(name, simulate=True)
    assert result["passed"] is True
    assert result["score"] == 1.0


def test_print_summary_smoke(capsys):
    name = _named("db")
    print_summary(
        [
            {
                "scenario": name,
                "root_cause_match": True,
                "remediation_match": False,
                "score": 0.5,
                "passed": False,
            }
        ]
    )
    out = capsys.readouterr().out
    assert name in out
    assert "FAIL" in out
