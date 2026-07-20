"""FastAPI webhook server for Alertmanager → AutoSRE."""

from __future__ import annotations

import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from autosre.bootstrap import load_env
from autosre.config import AutoSREConfig
from autosre.logging import TraceContext, setup_logging
from autosre.store import IncidentStore

load_env()

logger = logging.getLogger(__name__)

_queue: Optional[asyncio.Queue] = None
_worker_task: Optional[asyncio.Task] = None


def _first_firing_alert(payload: dict) -> Optional[dict]:
    alerts = payload.get("alerts") or []
    for alert in alerts:
        if (alert.get("status") or "firing").lower() == "firing":
            return alert
    return alerts[0] if alerts else None


def _map_alertmanager_to_scenario(payload: dict) -> Optional[str]:
    """Map an Alertmanager payload onto a scenario using catalog metadata only."""
    from scenarios import SCENARIOS

    alert = _first_firing_alert(payload)
    if not alert:
        return None

    labels = alert.get("labels") or {}
    annotations = alert.get("annotations") or {}

    for key in ("scenario", "autosre_scenario", "fault"):
        if labels.get(key) in SCENARIOS:
            return labels[key]

    service = labels.get("service") or labels.get("job") or ""
    summary = (
        annotations.get("summary")
        or annotations.get("description")
        or ""
    ).lower()
    alertname = (labels.get("alertname") or "").lower()
    blob = f"{alertname} {summary} {service}".lower()

    # Prefer exact service match from the scenario catalog.
    for name, scenario in SCENARIOS.items():
        if service and scenario.get("service") == service:
            return name

    # Match optional webhook_labels declared on each scenario (no hardcoding).
    for name, scenario in SCENARIOS.items():
        wanted = scenario.get("webhook_labels") or {}
        if wanted and all(str(labels.get(k, "")).lower() == str(v).lower() for k, v in wanted.items()):
            return name

    # Keyword match from scenario.webhook_keywords (fixture-driven).
    for name, scenario in SCENARIOS.items():
        keywords = [k.lower() for k in (scenario.get("webhook_keywords") or [])]
        if keywords and any(k in blob for k in keywords):
            return name

    return None


def _check_webhook_auth(request: Request, cfg: AutoSREConfig) -> Optional[JSONResponse]:
    """Return a 401 response if webhook token is configured and missing/invalid."""
    expected = cfg.webhook_token
    if not expected:
        return None
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return JSONResponse(
            status_code=401,
            content={"status": "unauthorized", "detail": "Bearer token required"},
        )
    provided = auth.split(" ", 1)[1].strip()
    if not hmac.compare_digest(provided, expected):
        return JSONResponse(
            status_code=401,
            content={"status": "unauthorized", "detail": "invalid token"},
        )
    return None


async def _incident_worker(queue: asyncio.Queue, app: FastAPI) -> None:
    """Process queued incidents one at a time."""
    while True:
        item = await queue.get()
        app.state.busy = True
        try:
            scenario = item.get("scenario")
            logger.info("Worker picked up scenario=%s", scenario)
            import autosre.agent as agent_mod

            with TraceContext(item.get("trace_id")):
                await asyncio.to_thread(agent_mod.run_agent, scenario, False)
        except Exception as exc:
            logger.exception("Worker failed for item %s: %s", item, exc)
        finally:
            app.state.busy = False
            queue.task_done()


def create_app(cfg: Optional[AutoSREConfig] = None) -> FastAPI:
    """Build the FastAPI application."""
    cfg = cfg or AutoSREConfig.from_env()
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _queue, _worker_task
        _queue = asyncio.Queue(maxsize=1)
        app.state.queue = _queue
        app.state.cfg = cfg
        app.state.store = IncidentStore(cfg.db_path)
        app.state.busy = False
        _worker_task = asyncio.create_task(_incident_worker(_queue, app))
        logger.info("Webhook server started on configured port %s", cfg.port)
        yield
        if _worker_task:
            _worker_task.cancel()
            try:
                await _worker_task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title="AutoSRE", version="0.2.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "service": "autosre"}

    @app.get("/incidents")
    async def list_incidents(limit: int = 50) -> dict[str, Any]:
        store: IncidentStore = app.state.store
        return {"incidents": store.get_history(limit=limit)}

    @app.get("/incidents/{incident_id}")
    async def get_incident(incident_id: int) -> dict[str, Any]:
        store: IncidentStore = app.state.store
        row = store.get_incident(incident_id)
        if row is None:
            raise HTTPException(status_code=404, detail="incident not found")
        return {"incident": row}

    @app.post("/webhook/alertmanager")
    async def alertmanager_webhook(request: Request) -> JSONResponse:
        denied = _check_webhook_auth(request, app.state.cfg)
        if denied is not None:
            return denied

        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc

        scenario = _map_alertmanager_to_scenario(payload)
        if not scenario:
            raise HTTPException(
                status_code=422,
                detail="unable to map alert to a known AutoSRE scenario",
            )

        queue: asyncio.Queue = app.state.queue
        if app.state.busy or queue.full() or queue.qsize() > 0:
            return JSONResponse(
                status_code=429,
                content={
                    "status": "busy",
                    "detail": "an incident is already being processed",
                },
            )

        trace = TraceContext()
        item = {"scenario": scenario, "payload": payload, "trace_id": trace.trace_id}
        try:
            app.state.busy = True
            queue.put_nowait(item)
        except asyncio.QueueFull:
            app.state.busy = False
            return JSONResponse(
                status_code=429,
                content={
                    "status": "busy",
                    "detail": "an incident is already being processed",
                },
            )

        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "scenario": scenario,
                "trace_id": trace.trace_id,
            },
        )

    return app


app = create_app()
