# AutoSRE → Actual Production Pipeline

This is the **sequence of stages** required to go from today’s reference agent to something an SRE team could responsibly own. It is aligned with Production Readiness Review (PRR) practice: observability, reliability/SLOs, security, failure modes, change management, ownership — and autonomous-remediation extras (blast radius, policy gates, human-in-the-loop).

**Honest current stage:** Stage 2 (Hardened reference). Not Stage 5 (SRE-owned production).

---

## Stage 0 — Runnable closed loop (DONE)

**Requirement:** A laptop can run the full gather → diagnose → remediate → report loop against mocks.

| Gate | Evidence |
|------|----------|
| Scenarios + fixtures | `scenarios.json`, `fixtures/*` |
| Mock backends | `./start_services.sh` |
| Simulate / eval | `python agent.py --simulate`, `eval.py --simulate` |
| CI smoke | `.github/workflows/ci.yml` |

**Exit criteria:** CI green; simulate passes for every catalog scenario.

---

## Stage 1 — Hardened package (DONE)

**Requirement:** Code is modular, retried, logged, gated, and historically auditable at demo scale.

| Gate | Evidence |
|------|----------|
| Package layout | `autosre/` |
| Retries / timeout / fallback | `retry.py`, `config.py`, agent fallback chain |
| Approval modes | `approval.py` (`auto` / `prompt` / `webhook`) |
| Incident store | `store.py` SQLite |
| Webhook entry | `server.py` + `webhook.py` |

**Exit criteria:** Unit tests for store/approval/retry/webhook; no monolithic agent.

---

## Stage 2 — Integration-ready (IN PROGRESS / this PR)

**Requirement:** Can talk to *real* Prom/ES/AWX shapes with auth; failures persist; inbound webhook can require a token; remediations have a **policy** layer; package layout is clean.

| Gate | Requirement | Status |
|------|-------------|--------|
| Dotenv before config | No silent missing `.env` | Done |
| Backend adapters | `mock` vs PromQL / ES DSL / AWX | Done (unproven on live infra) |
| Outbound auth headers | Bearer / ApiKey injectable | Done |
| Durable failures | `failed` / `timeout` / `denied` rows | Done |
| Scenario thresholds | Rollback from `healthy_thresholds` | Done |
| Webhook Bearer | Optional token check | Done |
| **Clean backends package** | Adapters not stuffed in `tools.py` | **This push** |
| **Policy / blast-radius gate** | Allowlist + max hosts before execute | **This push** |
| **Readiness + self-metrics** | `/ready`, counters for incidents | **This push** |
| **Webhook rate limit + audit** | Abuse resistance + append-only audit log | **This push** |

**Exit criteria:** Adapters isolated; policy denies oversize blast radius; `/ready` fails on bad config; audit log written for remediations; CI green.

**Still NOT Stage 2 complete until:** at least one soak against a non-mock Prometheus *or* documented “staging stack” compose that exercises `BACKEND_MODE=real`.

---

## Stage 3 — Staging / pre-prod (NOT DONE)

**Requirement:** Run continuously against a staging cluster with real(ish) deps; prove failure modes.

| Step | Requirement | Replicable artifact |
|------|-------------|---------------------|
| 3.1 | Staging compose: Prometheus + Loki/ES + AWX-or-ansible-runner | `deploy/staging/` |
| 3.2 | Live eval job with secret LLM key (nightly) | CI workflow `eval-live.yml` |
| 3.3 | Chaos: kill mock mid-incident; assert timeout persisted | `tests/test_chaos.py` |
| 3.4 | Load: N concurrent webhooks → 429 / queue behavior measured | `scripts/load_webhook.py` |
| 3.5 | Secrets via env/file only; no tokens in git | checked |
| 3.6 | Runbooks for “agent down”, “queue stuck”, “bad remediation” | `docs/runbooks/` |

**Exit criteria:** 7-day staging soak with &lt;2 pages/day equivalent noise; postmortems for any staging outage.

---

## Stage 4 — Production-controlled autonomy (NOT DONE)

**Requirement:** Autonomous remediations are **risk-bounded** the way real AIOps products describe (blast radius score, policy-as-code, audit, rollback).

| Step | Requirement |
|------|-------------|
| 4.1 | Blast-radius model: hosts × services × playbook criticality → score |
| 4.2 | Policy engine (OPA or YAML policies): deny lists, change windows, env tags |
| 4.3 | Risk tiers: auto / notify-window / require-approval |
| 4.4 | Append-only audit export (JSONL → SIEM); hash chain optional |
| 4.5 | Idempotent remediations + automatic rollback on threshold breach |
| 4.6 | Multi-replica webhook with external queue (Redis/SQS), not in-process only |
| 4.7 | mTLS or HMAC on Alertmanager path; network policy |
| 4.8 | SLOs on agent: acceptance latency, success rate, remediation error rate |

**Exit criteria:** PRR document signed; only low-blast actions auto; high-blast always human-gated.

---

## Stage 5 — SRE-owned production (NOT DONE)

**Requirement:** Matches Google-style PRR ownership bar.

| Step | Requirement |
|------|-------------|
| 5.1 | SLOs + error budget + paging alerts on the *agent* |
| 5.2 | On-call rotation + escalation for AutoSRE itself |
| 5.3 | Canary deploys / staged rollout of agent versions |
| 5.4 | DR: DB backup/restore drill for incident history |
| 5.5 | Capacity plan for alert storms |
| 5.6 | Dependency failure matrix (LLM down, Prom down, AWX down) |
| 5.7 | Security review: authn/z, SSRF, secret scanning |
| 5.8 | Continuous readiness scorecard (not one-time checklist) |

**Exit criteria:** SRE team accepts on-call for the agent; Treynor-class page rate; postmortems for agent incidents.

---

## Replicable “definition of done” per stage

```text
Stage N is DONE only when:
  1. Checklist gates above are checked with linked evidence (test, doc, or dash)
  2. CI (and staging job if N≥3) is green on main
  3. A stranger can follow docs/runbooks and reproduce the gate
```

---

## What we implement next on this branch (real work)

1. **Clean layout** — `autosre/backends/` for mock/real HTTP adapters; `tools.py` stays thin dispatch.
2. **Policy gate** — max hosts, playbook allowlist from env/fixtures, deny with audit.
3. **Readiness** — `GET /ready` validates config; in-process counters for incidents.
4. **Webhook rate limit + JSONL audit** — basic abuse control + durable action log.

Stages 3–5 stay out of scope for this PR; they need staging infra and org process, not more demo code.
