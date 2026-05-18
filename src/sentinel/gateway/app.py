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
import os
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
from fastapi.responses import HTMLResponse, StreamingResponse
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

    # Per-IP rate limit on Gemini-spending endpoints. Disabled when
    # SENTINEL_ENV != "prod" so local dev / tests are unaffected.
    if get_settings().__class__ and os.environ.get("SENTINEL_ENV", "").lower() == "prod":
        from sentinel.gateway.rate_limit import RateLimitMiddleware
        app.add_middleware(RateLimitMiddleware)

    # Mount A2A — exposes /.well-known/agent.json + /a2a/v1/tasks/{send,id}
    from sentinel.a2a import a2a_router
    app.include_router(a2a_router)

    async def _load_agent_or_404(agent_id: str):
        try:
            return await load_agent(agent_id)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.get("/", response_class=HTMLResponse)
    async def root() -> str:
        """Landing page so judges who hit the public URL in a browser
        see something coherent instead of `{"detail":"Not Found"}`."""
        settings = get_settings()
        gemini_state = "live" if settings.gemini_api_key else "stub mode"
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Sentinel · Gateway</title>
<style>
  body {{
    background: #0B0E16; color: #E4E4E7;
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    margin: 0; padding: 64px 32px; max-width: 720px; margin-inline: auto;
    line-height: 1.6;
  }}
  h1 {{ font-family: "Iowan Old Style", Georgia, serif; color: #F97316; font-size: 56px; margin: 0 0 12px; letter-spacing: -0.02em; }}
  h1 .accent {{ font-style: italic; color: #F97316; }}
  .eyebrow {{ display: inline-block; color: #F97316; border: 1px solid rgba(249,115,22,0.4); background: rgba(249,115,22,0.06); padding: 4px 10px; border-radius: 4px; font: 600 11px/1 "JetBrains Mono", ui-monospace, monospace; letter-spacing: 0.18em; text-transform: uppercase; margin-bottom: 24px; }}
  .rule {{ width: 56px; height: 2px; background: #F97316; margin: 22px 0; }}
  p.lead {{ font-size: 19px; color: #D4D4D8; }}
  a {{ color: #FDBA74; }}
  code {{ font-family: "JetBrains Mono", ui-monospace, monospace; background: rgba(249,115,22,0.10); border: 1px solid rgba(249,115,22,0.22); color: #FED7AA; padding: 1px 6px; border-radius: 4px; font-size: 0.9em; }}
  .endpoints {{ display: grid; gap: 8px; margin: 24px 0; }}
  .endpoints a {{ display: flex; gap: 12px; padding: 12px 16px; background: rgba(20,22,32,0.7); border: 1px solid rgba(249,115,22,0.18); border-radius: 8px; text-decoration: none; color: #E4E4E7; font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 13px; }}
  .endpoints a:hover {{ border-color: rgba(249,115,22,0.5); }}
  .method {{ color: #F97316; font-weight: 600; }}
  .desc {{ color: #A1A1AA; margin-left: auto; font-size: 12px; }}
  footer {{ margin-top: 48px; font: 11px/1.5 "JetBrains Mono", ui-monospace, monospace; color: #71717A; letter-spacing: 0.12em; text-transform: uppercase; }}
</style>
</head>
<body>
  <span class="eyebrow">Governance Plane · {gemini_state}</span>
  <h1>Agent <span class="accent">Sentinel</span></h1>
  <div class="rule"></div>
  <p class="lead">
    Gemini-powered governance plane that gates every AI agent tool call,
    signs the audit trail, and meters per-business-unit spend. This is the
    live gateway service. The dashboard is a separate service.
  </p>

  <h3 style="color:#F97316; font-size:14px; letter-spacing:0.14em; text-transform:uppercase; font-family:'JetBrains Mono',ui-monospace,monospace;">Public endpoints</h3>
  <div class="endpoints">
    <a href="/healthz"><span class="method">GET</span> /healthz <span class="desc">liveness + Gemini state</span></a>
    <a href="/.well-known/agent.json"><span class="method">GET</span> /.well-known/agent.json <span class="desc">A2A discovery card</span></a>
    <a href="/v1/receipts?limit=20"><span class="method">GET</span> /v1/receipts <span class="desc">filterable audit trail</span></a>
    <a href="/v1/cost/rollup?days=7"><span class="method">GET</span> /v1/cost/rollup <span class="desc">per-BU spend</span></a>
    <a href="/v1/policies"><span class="method">GET</span> /v1/policies <span class="desc">policy library</span></a>
    <a href="/v1/anchors"><span class="method">GET</span> /v1/anchors <span class="desc">Merkle anchor batches</span></a>
  </div>

  <h3 style="color:#F97316; font-size:14px; letter-spacing:0.14em; text-transform:uppercase; font-family:'JetBrains Mono',ui-monospace,monospace;">Try a tool call</h3>
  <pre style="background:rgba(20,22,32,0.85); border:1px solid rgba(249,115,22,0.18); border-radius:8px; padding:18px 22px; overflow-x:auto; font-size:12.5px; color:#E4E4E7;">curl -X POST https://agent-sentinel.up.railway.app/v1/tools/call \\
  -H 'content-type: application/json' \\
  -d '{{"agent_id":"agent-sales-01","session_id":"hi","tool":"web.search","args":{{"q":"competitor pricing 2026"}}}}'</pre>

  <p style="color:#A1A1AA; font-size:14px;">
    Per-IP rate limit: 30 req/min, 500 req/day on Gemini-spending endpoints.
    Clone <a href="https://github.com/SankarSubbayya/agent_sentinel">github.com/SankarSubbayya/agent_sentinel</a> and run locally for unlimited use.
  </p>

  <footer>
    Sankar Subbayya · MIT · Transforming Enterprise Through AI hackathon · May 2026
  </footer>
</body>
</html>"""

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

    @app.post("/v1/observe")
    async def observe(call: ToolCallRequest) -> dict[str, Any]:
        """AuditLens / observe-only mode — record the call as a receipt
        marked `observed_only=true` WITHOUT gating it. The agent's action
        is allowed to proceed unaltered; Sentinel becomes a passive
        observer. Useful for organizations migrating from 'log everything'
        toward inline enforcement."""
        from sentinel.audit import ReceiptInput, write_receipt
        from sentinel.audit.ledger import hash_args
        if not call.agent_id:
            raise HTTPException(400, "agent_id required")
        agent = await _load_agent_or_404(call.agent_id)
        receipt_id = await write_receipt(
            ReceiptInput(
                agent_id=agent.agent_id,
                session_id=call.session_id,
                tool=call.tool,
                args_hash=hash_args(call.args),
                decision="allow",  # observe mode is always pass-through
                decided_by="static",
                confidence=None,
                escalated=False,
                rationale="observed-only mode — no gating applied",
                latency_ms=0,
                observed_only=True,
            )
        )
        return {"receipt_id": str(receipt_id), "mode": "observe"}

    @app.post("/v1/policies/text")
    async def upload_policy_text(payload: dict[str, Any]) -> dict[str, Any]:
        """Author a policy as raw text (no PDF). Lower-cost path to ingest
        policy content from the dashboard or a CMS. PolicyPipe still stamps
        the cache_id when a Gemini key is configured; otherwise the policy
        is registered in the catalog and Pro reasons over its inline summary."""
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td

        from sqlalchemy import text as _text

        from sentinel.db import get_session as _gs

        name = (payload.get("name") or "").strip()
        version = (payload.get("version") or "").strip()
        body = (payload.get("body") or "").strip()
        domain_tags = payload.get("domain_tags") or []
        if not name or not version or not body:
            raise HTTPException(400, "name, version, and body are required")

        # Reuse the catalog upsert path.
        from hashlib import sha256
        sha = sha256(body.encode("utf-8")).hexdigest()
        async with _gs() as s:
            row = (await s.execute(
                _text(
                    """
                    INSERT INTO policy_docs
                      (name, version, domain_tags, summary, source_sha256, source_text)
                    VALUES (:n, :v, :tags, :sum, :sha, :body)
                    ON CONFLICT (name, version) DO UPDATE SET
                      domain_tags  = EXCLUDED.domain_tags,
                      summary      = EXCLUDED.summary,
                      source_text  = EXCLUDED.source_text,
                      source_sha256 = EXCLUDED.source_sha256
                    RETURNING id
                    """
                ),
                {"n": name, "v": version, "tags": domain_tags,
                 "sum": body[:400], "sha": sha, "body": body},
            )).first()
            await s.commit()

        return {
            "id": str(row[0]),
            "name": name,
            "version": version,
            "domain_tags": domain_tags,
        }

    @app.post("/v1/ledger/verify")
    async def ledger_verify(payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """HTTP-callable version of `sentinel ledger verify`. Runs the
        hash-chain + signature check in the gateway's event loop and
        returns a JSON report. Used by the integration test suite
        (which can't easily share asyncpg connections across pytest
        event loops) and by any external auditor with HTTP access."""
        from dataclasses import asdict
        from sentinel.audit.verify import verify
        agent = (payload or {}).get("agent_id")
        report = await verify(source="db", agent_id=agent)
        return {
            "total": report.total,
            "verified": report.verified,
            "all_ok": report.all_ok,
            "chains": report.chains,
            "tampered": [asdict(v) for v in report.tampered],
        }

    @app.post("/v1/_test/truncate")
    async def _test_truncate() -> dict[str, Any]:
        """Test-only: wipe audit tables for deterministic integration runs.
        Returns row counts before truncation. Gated by SENTINEL_ENV != 'prod'."""
        import os
        if os.environ.get("SENTINEL_ENV", "dev").lower() == "prod":
            raise HTTPException(403, "truncate disabled in production")
        from sqlalchemy import text as _text
        from sentinel.db import get_session as _gs
        async with _gs() as s:
            counts = {}
            for t in ("audit_receipts", "cost_events", "alert_events", "anchor_batches"):
                row = (await s.execute(_text(f"SELECT count(*) FROM {t}"))).scalar()
                counts[t] = int(row or 0)
            await s.execute(_text(
                "TRUNCATE alert_events, anchor_batches, cost_events, "
                "audit_receipts RESTART IDENTITY CASCADE"
            ))
            await s.commit()
        return {"before": counts, "truncated": True}

    @app.post("/v1/_test/tamper")
    async def _test_tamper(payload: dict[str, Any]) -> dict[str, Any]:
        """Test-only: mutate the rationale of a specific receipt and return
        the original so the test can restore. Gated by SENTINEL_ENV != 'prod'."""
        import os
        if os.environ.get("SENTINEL_ENV", "dev").lower() == "prod":
            raise HTTPException(403, "tamper disabled in production")
        receipt_id = payload.get("receipt_id")
        new_rationale = payload.get("rationale", "[tampered]")
        if not receipt_id:
            raise HTTPException(400, "receipt_id required")
        from sqlalchemy import text as _text
        from sentinel.db import get_session as _gs
        async with _gs() as s:
            row = (await s.execute(
                _text("SELECT rationale FROM audit_receipts WHERE receipt_id = :r"),
                {"r": receipt_id},
            )).first()
            if not row:
                raise HTTPException(404, f"receipt {receipt_id} not found")
            original = row[0]
            await s.execute(
                _text("UPDATE audit_receipts SET rationale = :v WHERE receipt_id = :r"),
                {"v": new_rationale, "r": receipt_id},
            )
            await s.commit()
        return {"receipt_id": receipt_id, "original_rationale": original}

    @app.get("/v1/anchors")
    async def list_anchor_batches(limit: int = Query(default=50, le=200)) -> dict[str, Any]:
        from sentinel.anchoring import list_anchors
        return {"anchors": await list_anchors(limit=limit)}

    @app.post("/v1/anchors/run")
    async def run_anchor(payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from sentinel.anchoring import anchor_pending
        target = (payload or {}).get("target", "local")
        result = await anchor_pending(target=target)
        return {
            "batch_id": str(result.batch_id),
            "merkle_root": result.merkle_root,
            "receipt_count": result.receipt_count,
            "anchor_target": result.anchor_target,
            "anchor_pointer": result.anchor_pointer,
        }

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
