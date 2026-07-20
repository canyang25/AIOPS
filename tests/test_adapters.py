"""Tests for HTTP auth headers and real-backend adapters."""

from unittest.mock import MagicMock, patch

from scenarios import SCENARIOS
from autosre.config import AutoSREConfig
from autosre.tools import _tool_query_metrics, _tool_run_playbook, _tool_search_logs


def _any_scenario():
    name = sorted(SCENARIOS.keys())[0]
    return name, SCENARIOS[name]


def test_config_request_headers_include_authorization(monkeypatch):
    monkeypatch.setenv("AUTOSRE_HTTP_AUTHORIZATION", "Bearer unit-token")
    monkeypatch.setenv("AUTOSRE_HTTP_HEADERS_JSON", '{"X-Env":"test"}')
    cfg = AutoSREConfig.from_env()
    headers = cfg.request_headers()
    assert headers["Authorization"] == "Bearer unit-token"
    assert headers["X-Env"] == "test"


def test_mock_query_sends_auth_header():
    _, scenario = _any_scenario()
    metric = scenario["metrics"].split(",")[0].strip()
    service = scenario["service"]

    cfg = AutoSREConfig(
        backend_mode="mock",
        prometheus_url="http://prometheus.test",
        http_authorization="Bearer mock-token",
    )

    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "data": {"result": [{"values": [[1, 10], [2, 20]]}]}
        }
        return resp

    with patch("autosre.backends.http.requests.get", side_effect=fake_get):
        result = _tool_query_metrics(service, metric, cfg=cfg)

    assert captured["headers"]["Authorization"] == "Bearer mock-token"
    assert captured["params"]["service"] == service
    assert captured["params"]["metric"] == metric
    assert result["latest"] == 20


def test_real_prometheus_uses_promql_params():
    _, scenario = _any_scenario()
    metric = scenario["metrics"].split(",")[0].strip()
    service = scenario["service"]

    cfg = AutoSREConfig(
        backend_mode="real",
        prometheus_url="http://prometheus.test",
        http_authorization="Bearer prom-token",
        prometheus_query_template='{metric}{{service="{service}"}}',
    )

    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        captured["headers"] = headers
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "data": {"result": [{"values": [[1, "1.5"], [2, "2.5"]]}]}
        }
        return resp

    with patch("autosre.backends.http.requests.get", side_effect=fake_get):
        result = _tool_query_metrics(service, metric, cfg=cfg)

    assert "query" in captured["params"]
    assert "start" in captured["params"]
    assert "end" in captured["params"]
    assert "step" in captured["params"]
    assert service in captured["params"]["query"]
    assert metric in captured["params"]["query"]
    assert captured["headers"]["Authorization"] == "Bearer prom-token"
    assert result["latest"] == 2.5


def test_real_awx_launch_uses_template_map():
    name = sorted(SCENARIOS.keys())[0]
    playbook = SCENARIOS[name]["expected_remediation"].split()[0]
    cfg = AutoSREConfig(
        backend_mode="real",
        ansible_url="http://awx.test",
        http_authorization="Bearer awx-token",
        awx_job_template_map={playbook: "42"},
    )

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        resp = MagicMock()
        resp.status_code = 201
        resp.content = b"{}"
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"job": 99, "id": 99}
        return resp

    with patch("autosre.backends.http.requests.post", side_effect=fake_post):
        result = _tool_run_playbook(playbook, hosts=["host-a"], cfg=cfg)

    assert captured["url"].endswith("/api/v2/job_templates/42/launch/")
    assert captured["headers"]["Authorization"] == "Bearer awx-token"
    assert result["job"] == 99


def test_real_elk_uses_index_search():
    _, scenario = _any_scenario()
    cfg = AutoSREConfig(
        backend_mode="real",
        elk_url="http://es.test",
        elk_index="logs-prod",
        http_authorization="ApiKey xyz",
    )

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"{}"
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "hits": {"total": {"value": 1}, "hits": [{"_source": {"message": "x"}}]}
        }
        return resp

    with patch("autosre.backends.http.requests.post", side_effect=fake_post):
        result = _tool_search_logs(scenario["service"], level="ERROR", cfg=cfg)

    assert captured["url"].endswith("/logs-prod/_search")
    assert captured["headers"]["Authorization"] == "ApiKey xyz"
    assert result["total"] == 1
