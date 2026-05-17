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

from dataclasses import asdict

from sentinel.agent_runner import AgentRunRequest, run_agent
from sentinel.audit import query_receipts
from sentinel.config import get_settings
from sentinel.cost import bu_rollup
from sentinel.db import init_schema
from sentinel.gateway.pipeline import gate_and_record, load_agent
from sentinel.models import ToolCallRequest, ToolCallResponse
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

    async def _load_agent_or_404(agent_id: str):
        try:
            return await load_agent(agent_id)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))

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
        if not call.agent_id:
            raise HTTPException(400, "agent_id required (JWT auth not enabled in dev)")
        agent = await _load_agent_or_404(call.agent_id)
        result = await gate_and_record(call, agent)
        return result.response

    @app.post("/v1/agents/run")
    async def agents_run(req: dict[str, Any]) -> dict[str, Any]:
        """Drive an LLM agent for a single brief. Every tool call flows
        through the same gate_and_record pipeline as POST /v1/tools/call."""
        agent_id = req.get("agent_id")
        brief = req.get("brief")
        max_steps = int(req.get("max_steps", 6))
        if not agent_id or not brief:
            raise HTTPException(400, "agent_id and brief are required")
        # Validate the agent exists up front so a 404 is returned cleanly.
        await _load_agent_or_404(agent_id)
        result = await run_agent(
            AgentRunRequest(agent_id=agent_id, brief=brief, max_steps=max_steps)
        )
        # Dataclasses -> dicts for JSON response.
        return {
            "agent_id": result.agent_id,
            "session_id": result.session_id,
            "brief": result.brief,
            "mode": result.mode,
            "final_message": result.final_message,
            "total_cost_usd": result.total_cost_usd,
            "steps": [asdict(s) for s in result.steps],
        }

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
