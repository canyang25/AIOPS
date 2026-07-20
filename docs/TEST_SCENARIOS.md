# Production readiness — fixture-driven test scenarios

These are the cases to keep green. Inputs come from `scenarios.json` / `fixtures/*`.
Do **not** hardcode alert IDs, playbook names, or thresholds in tests; load them from the catalog.

| ID | Area | Setup | Assert |
|----|------|-------|--------|
| T1 | dotenv/config | Env vars for port/auth | `AutoSREConfig.from_env()` reflects env |
| T2 | auth headers | `AUTOSRE_HTTP_AUTHORIZATION` set | Outbound tool call includes `Authorization` |
| T3 | prometheus adapter | `BACKEND_MODE=real` | Query params include `query`/`start`/`end`/`step` |
| T4 | persist failure | Force LLM backend raise | Store row `status=failed` for scenario alert_id |
| T5 | rollback healthy | Metric latest under scenario threshold | No rollback `_dispatch` |
| T6 | rollback unhealthy | Metric latest over scenario threshold | Rollback playbook invoked once |
| T7 | webhook 401 | Token configured; bad/missing Bearer | HTTP 401 |
| T8 | webhook 202 | Valid Bearer + payload from `SCENARIOS` | 202 + mapped scenario name |
| T9 | incidents get | Save via store; `GET /incidents/{id}` | Body matches catalog alert_id |
| T10 | catalog parity | Load `scenarios.json` | `SCENARIOS.keys()` equals JSON keys |
| T11 | eval keywords | Report text from scenario `expected_*` | Partial/full score |
| T12 | simulate all | Every catalog scenario | `simulate(name) == 0` |

See also: `/opt/cursor/artifacts/plans/autosre_production_readiness_7f2a.plan.md`
