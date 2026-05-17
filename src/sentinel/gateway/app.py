"""FastAPI app — the only HTTP surface.

Pipeline per request:
  static engine -> (if pass) flash gate -> (if escalate/low-conf/drift) pro escalation
  -> audit receipt -> cost event -> response.

Endpoints:
  POST /v1/tools/call         — gateway (the main loop)
  GET  /v1/receipts           — filterable receipt browser
  GET  /v1/cost/rollup        — BU spend rollup
  GET  /v1/policies           — list policy docs
  POST /v1/policies/upload    — upload + ingest via PolicyPipe (multipart)
  GET  /v1/events/stream      — Server-Sent Events live timeline
  GET  /healthz               — liveness
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from sentinel.audit import ReceiptInput, query_receipts, write_receipt
from sentinel.audit.ledger import fetch_recent_for_agent, hash_args
from sentinel.config import get_settings
from sentinel.cost import bu_rollup, compute_cost, write_cost_event
from sentinel.db import get_session, init_schema
from sentinel.gating import (
    drift_signal,
    evaluate_static,
    flash_gate,
    pro_escalation,
)
from sentinel.gating.static_engine import StaticVerdict
from sentinel.models import AgentRecord, ToolCallRequest, ToolCallResponse
from sentinel.policy_pipe import list_docs

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_schema()
    log.info("sentinel.start", schema="ready")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Sentinel", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def _load_agent(agent_id: str) -> AgentRecord:
        async with get_session() as s:
            result = await s.execute(
                text(
                    "SELECT agent_id, name, bu, role, declared_goal "
                    "FROM agents WHERE agent_id = :a"
                ),
                {"a": agent_id},
            )
            row = result.mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Unknown agent_id '{agent_id}'")
        return AgentRecord(**dict(row))

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        settings = get_settings()
        return {
            "status": "ok",
            "gemini_configured": bool(settings.gemini_api_key),
            "flash_model": settings.flash_model,
            "pro_model": settings.pro_model,
        }

    @app.post("/v1/tools/call", response_model=ToolCallResponse)
    async def tools_call(call: ToolCallRequest) -> ToolCallResponse:
        t0 = time.perf_counter()

        if not call.agent_id:
            raise HTTPException(400, "agent_id required (JWT auth not enabled in dev)")
        agent = await _load_agent(call.agent_id)

        # ---- 1) Static engine
        verdict: StaticVerdict = evaluate_static(call, agent)
        decided_by: str = "static"
        decision: str = verdict.decision  # "allow" | "deny" | "pass"
        confidence: float | None = None
        escalated = False
        rationale = verdict.rationale
        rewritten_args: dict[str, Any] | None = None
        policy_versions: list[dict[str, str]] = []
        cache_ids: list[str] = []

        # Recent history feeds both the drift detector and Pro.
        recent = await fetch_recent_for_agent(agent.agent_id, limit=20)

        # ---- 2) Drift signal (always cheap)
        drift_escalate, drift_reason = drift_signal(call, agent, recent)

        # ---- 3) Flash gate if static didn't fire
        if verdict.decision == "pass":
            gd = await flash_gate(call, agent)
            decided_by = "flash"
            decision = gd.decision
            confidence = gd.confidence
            escalated = gd.escalate or drift_escalate
            rationale = gd.rationale
            rewritten_args = gd.rewritten_args

            # ---- 4) Pro escalation when Flash flagged it, drift fired, or low conf
            settings = get_settings()
            need_pro = (
                escalated
                or (confidence is not None and confidence < settings.flash_escalate_threshold)
            )
            if need_pro:
                pro_decision, pol_versions, cids = await pro_escalation(
                    call, agent, recent, flash_decision=gd
                )
                decided_by = "pro"
                decision = pro_decision.decision
                confidence = pro_decision.confidence
                rationale = pro_decision.rationale
                rewritten_args = pro_decision.rewritten_args
                policy_versions = pol_versions
                cache_ids = cids
                if drift_reason:
                    rationale = f"[drift:{drift_reason}] {rationale}"

        latency_ms = int((time.perf_counter() - t0) * 1000)

        # ---- 5) Audit
        receipt_id = await write_receipt(
            ReceiptInput(
                agent_id=agent.agent_id,
                session_id=call.session_id,
                tool=call.tool,
                args_hash=hash_args(call.args),
                decision=decision,  # type: ignore[arg-type]
                decided_by=decided_by,  # type: ignore[arg-type]
                confidence=confidence,
                escalated=escalated,
                rationale=rationale,
                latency_ms=latency_ms,
                policy_versions_used=policy_versions,
                gemini_cache_ids=cache_ids,
            )
        )

        # ---- 6) Cost
        base, gemini, total = compute_cost(decided_by, escalated, decision)
        await write_cost_event(
            receipt_id=receipt_id,
            bu=agent.bu,
            tool=call.tool,
            base_cost=base,
            gemini_cost=gemini,
            total_cost=total,
        )

        log.info(
            "sentinel.decision",
            agent=agent.agent_id,
            tool=call.tool,
            decision=decision,
            decided_by=decided_by,
            escalated=escalated,
            latency_ms=latency_ms,
            cost_usd=total,
        )

        return ToolCallResponse(
            decision=decision,  # type: ignore[arg-type]
            receipt_id=receipt_id,
            rationale=rationale,
            rewritten_args=rewritten_args,
            cost_usd=total,
            latency_ms=latency_ms,
        )

    @app.get("/v1/receipts")
    async def get_receipts(
        agent_id: str | None = Query(default=None),
        bu: str | None = Query(default=None),
        tool: str | None = Query(default=None),
        decision: str | None = Query(default=None),
        limit: int = Query(default=100, le=500),
    ) -> dict[str, Any]:
        rows = await query_receipts(
            agent_id=agent_id, bu=bu, tool=tool, decision=decision, limit=limit
        )
        # Convert UUID/datetime for JSON.
        for r in rows:
            r["receipt_id"] = str(r["receipt_id"])
            if isinstance(r.get("created_at"), datetime):
                r["created_at"] = r["created_at"].isoformat()
        return {"receipts": rows, "count": len(rows)}

    @app.get("/v1/cost/rollup")
    async def get_cost_rollup(days: int = Query(default=7, ge=1, le=365)) -> dict[str, Any]:
        return {"days": days, "rows": await bu_rollup(days=days)}

    @app.get("/v1/policies")
    async def get_policies() -> dict[str, Any]:
        rows = await list_docs()
        for r in rows:
            r["id"] = str(r["id"])
            for k in ("effective_date", "cache_expires_at", "created_at"):
                if isinstance(r.get(k), (datetime,)):
                    r[k] = r[k].isoformat()
                elif r.get(k) is not None:
                    r[k] = str(r[k])
        return {"policies": rows, "count": len(rows)}

    @app.post("/v1/policies/upload")
    async def upload_policy(
        file: UploadFile = File(...),
        ttl_seconds: int = Form(21_600),
    ) -> dict[str, Any]:
        """Ingest a PDF: extractor -> catalog -> cache_builder. Requires GEMINI_API_KEY."""
        from sentinel.policy_pipe.cache_builder import build_cache_for_pdf
        from sentinel.policy_pipe.catalog import insert_or_update_doc, set_cache
        from sentinel.policy_pipe.extractor import extract_pdf

        if not get_settings().gemini_api_key:
            raise HTTPException(503, "GEMINI_API_KEY not configured; ingestion disabled")

        suffix = Path(file.filename or "policy.pdf").suffix or ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)

        try:
            doc = await extract_pdf(tmp_path)
            doc_id = await insert_or_update_doc(doc)
            file_id, cache_name, expires_at = await build_cache_for_pdf(
                tmp_path, display_name=f"{doc.name}-{doc.version}", ttl_seconds=ttl_seconds
            )
            await set_cache(doc_id, file_id, cache_name, expires_at)
        finally:
            tmp_path.unlink(missing_ok=True)

        return {
            "id": str(doc_id),
            "name": doc.name,
            "version": doc.version,
            "domain_tags": doc.domain_tags,
            "cache_id": cache_name,
            "cache_expires_at": expires_at.isoformat(),
        }

    @app.get("/v1/events/stream")
    async def events_stream() -> StreamingResponse:
        """SSE — emits {receipt} per new decision. Simple poll-then-diff."""

        async def gen():
            seen: set[str] = set()
            # Prime the seen set so we don't dump history on connect.
            primed = await query_receipts(limit=50)
            for r in primed:
                seen.add(str(r["receipt_id"]))

            yield f"event: hello\ndata: {json.dumps({'primed': len(seen)})}\n\n"

            while True:
                latest = await query_receipts(limit=50)
                new_rows = [r for r in latest if str(r["receipt_id"]) not in seen]
                # Emit oldest-first so the UI appends in order.
                for r in reversed(new_rows):
                    seen.add(str(r["receipt_id"]))
                    payload = dict(r)
                    payload["receipt_id"] = str(payload["receipt_id"])
                    if isinstance(payload.get("created_at"), datetime):
                        payload["created_at"] = payload["created_at"].isoformat()
                    yield f"event: receipt\ndata: {json.dumps(payload, default=str)}\n\n"
                await asyncio.sleep(1.0)

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


app = create_app()
