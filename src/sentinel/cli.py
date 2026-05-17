"""Sentinel CLI — `sentinel <subcommand>`.

Subcommands:
  serve                   run uvicorn against the gateway app
  init-db                 apply sql/001_init.sql to DATABASE_URL
  policy upload <pdf>     ingest a policy PDF via PolicyPipe
  policy list             list known policies
  agent register ...      add an agent row
  ledger export           dump receipts as JSONL
  demo run                walk the PRD demo script against a running gateway
  demo seed-policies      generate three example policy PDFs into ./demo_policies/
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sentinel.config import get_settings


# ---- serve

def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "sentinel.gateway:app",
        host=args.host or get_settings().sentinel_host,
        port=args.port or get_settings().sentinel_port,
        log_level=args.log_level,
        reload=args.reload,
    )
    return 0


# ---- init-db

async def _async_init_db() -> int:
    from sentinel.db import init_schema

    await init_schema()
    print("schema applied")
    return 0


def _cmd_init_db(_: argparse.Namespace) -> int:
    return asyncio.run(_async_init_db())


# ---- policy upload

async def _async_policy_upload(pdf_path: Path, ttl_s: int) -> int:
    from sentinel.policy_pipe.cache_builder import build_cache_for_pdf
    from sentinel.policy_pipe.catalog import insert_or_update_doc, set_cache
    from sentinel.policy_pipe.extractor import extract_pdf

    if not get_settings().gemini_api_key:
        print("ERROR: GEMINI_API_KEY required for policy ingestion", file=sys.stderr)
        return 1
    doc = await extract_pdf(pdf_path)
    print(f"extracted: {doc.name} {doc.version} tags={doc.domain_tags}")
    doc_id = await insert_or_update_doc(doc)
    file_id, cache_name, exp = await build_cache_for_pdf(
        pdf_path, display_name=f"{doc.name}-{doc.version}", ttl_seconds=ttl_s
    )
    await set_cache(doc_id, file_id, cache_name, exp)
    print(f"cached: id={doc_id} cache={cache_name} expires={exp.isoformat()}")
    return 0


def _cmd_policy_upload(args: argparse.Namespace) -> int:
    return asyncio.run(_async_policy_upload(Path(args.pdf).resolve(), args.ttl))


# ---- policy list

async def _async_policy_list() -> int:
    from sentinel.policy_pipe import list_docs

    rows = await list_docs()
    if not rows:
        print("(no policies ingested)")
        return 0
    for r in rows:
        print(
            f"{r['name']:<32} {r['version']:<10} "
            f"tags={r['domain_tags']!s:<32} cache={r['cache_id'] or '-'}"
        )
    return 0


def _cmd_policy_list(_: argparse.Namespace) -> int:
    return asyncio.run(_async_policy_list())


# ---- agent register

async def _async_agent_register(
    agent_id: str, name: str, bu: str, role: str, goal: str | None
) -> int:
    from sqlalchemy import text

    from sentinel.db import get_session

    async with get_session() as s:
        await s.execute(
            text(
                """
                INSERT INTO agents (agent_id, name, bu, role, declared_goal)
                VALUES (:a, :n, :b, :r, :g)
                ON CONFLICT (agent_id) DO UPDATE SET
                  name = EXCLUDED.name, bu = EXCLUDED.bu,
                  role = EXCLUDED.role, declared_goal = EXCLUDED.declared_goal
                """
            ),
            {"a": agent_id, "n": name, "b": bu, "r": role, "g": goal},
        )
        await s.commit()
    print(f"registered: {agent_id} ({role} in {bu})")
    return 0


def _cmd_agent_register(args: argparse.Namespace) -> int:
    return asyncio.run(
        _async_agent_register(args.agent_id, args.name, args.bu, args.role, args.goal)
    )


# ---- ledger export

async def _async_ledger_export(out: Path, limit: int) -> int:
    from sentinel.audit import query_receipts

    rows = await query_receipts(limit=limit)
    with out.open("w") as f:
        for r in rows:
            r["receipt_id"] = str(r["receipt_id"])
            if "created_at" in r and r["created_at"] is not None:
                r["created_at"] = str(r["created_at"])
            f.write(json.dumps(r, default=str) + "\n")
    print(f"wrote {len(rows)} receipts to {out}")
    return 0


def _cmd_ledger_export(args: argparse.Namespace) -> int:
    return asyncio.run(_async_ledger_export(Path(args.out), args.limit))


# ---- agent run

async def _async_agent_run(agent_id: str, brief: str, max_steps: int) -> int:
    from sentinel.agent_runner import AgentRunRequest, run_agent

    result = await run_agent(
        AgentRunRequest(agent_id=agent_id, brief=brief, max_steps=max_steps)
    )
    print(f"Agent: {result.agent_id}  session: {result.session_id}  mode: {result.mode}")
    print(f"Brief: {result.brief}\n")
    for s in result.steps:
        if s.kind == "tool_call":
            tag = (
                "ALLOW" if s.decision == "allow"
                else "DENY " if s.decision == "deny"
                else "REWR "
            )
            print(
                f"  [{s.step:>2}] {tag}  {s.tool:<24} "
                f"by={s.decided_by:<6} {s.latency_ms}ms  ${s.cost_usd:.5f}"
            )
            print(f"        rationale: {(s.rationale or '')[:120]}")
            if s.tool_result:
                print(f"        result:    {s.tool_result[:120]}")
        elif s.kind == "final":
            print(f"\n  final: {s.final_message}")
    print(f"\nTotal spend: ${result.total_cost_usd:.5f}")
    return 0


def _cmd_agent_run(args: argparse.Namespace) -> int:
    return asyncio.run(_async_agent_run(args.agent_id, args.brief, args.max_steps))


# ---- demo run

async def _async_demo_run(sentinel_url: str) -> int:
    from sentinel.demo_agents import DEMO_SCRIPT, run_demo_beat

    print(f"Running {len(DEMO_SCRIPT)} beats against {sentinel_url}\n")
    for beat in DEMO_SCRIPT:
        result = await run_demo_beat(beat, sentinel_url)
        ok = result.response.get("decision") == beat.expected_decision
        marker = "OK" if ok else "??"
        decision = result.response.get("decision", "?")
        latency = result.response.get("latency_ms", "?")
        rationale = result.response.get("rationale", "(no rationale)")
        print(f"[{marker}] {beat.name:<48} -> {decision:<8} ({latency}ms)")
        print(f"     {rationale[:140]}")
        print()
    return 0


def _cmd_demo_run(args: argparse.Namespace) -> int:
    return asyncio.run(_async_demo_run(args.sentinel_url))


# ---- demo seed-policies

def _cmd_demo_seed_policies(args: argparse.Namespace) -> int:
    from sentinel.demo_agents.seed_pdfs import write_demo_pdfs

    out_dir = Path(args.out_dir).resolve()
    paths = write_demo_pdfs(out_dir)
    for p in paths:
        print(f"wrote {p}")
    return 0


# ---- parser

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sentinel", description="Agent Sentinel CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run the gateway via uvicorn")
    s.add_argument("--host")
    s.add_argument("--port", type=int)
    s.add_argument("--log-level", default="info")
    s.add_argument("--reload", action="store_true")
    s.set_defaults(func=_cmd_serve)

    s = sub.add_parser("init-db", help="apply sql/001_init.sql")
    s.set_defaults(func=_cmd_init_db)

    pol = sub.add_parser("policy", help="policy library")
    polsub = pol.add_subparsers(dest="policy_cmd", required=True)
    s = polsub.add_parser("upload", help="ingest a PDF via PolicyPipe")
    s.add_argument("pdf")
    s.add_argument("--ttl", type=int, default=21_600)
    s.set_defaults(func=_cmd_policy_upload)
    s = polsub.add_parser("list", help="list known policies")
    s.set_defaults(func=_cmd_policy_list)

    ag = sub.add_parser("agent", help="agent registry + runner")
    agsub = ag.add_subparsers(dest="agent_cmd", required=True)
    s = agsub.add_parser("register", help="add/update an agent row")
    s.add_argument("agent_id")
    s.add_argument("--name", required=True)
    s.add_argument("--bu", required=True)
    s.add_argument("--role", required=True)
    s.add_argument("--goal")
    s.set_defaults(func=_cmd_agent_register)
    s = agsub.add_parser(
        "run",
        help="run an LLM agent against a brief; every tool call goes through Sentinel",
    )
    s.add_argument("agent_id", help="e.g. agent-sales-01 / agent-finance-01 / agent-ops-01")
    s.add_argument("brief", help="natural-language task description for the agent")
    s.add_argument("--max-steps", type=int, default=6)
    s.set_defaults(func=_cmd_agent_run)

    s = sub.add_parser("ledger", help="audit ledger")
    sub2 = s.add_subparsers(dest="ledger_cmd", required=True)
    e = sub2.add_parser("export", help="dump receipts as JSONL")
    e.add_argument("--out", default="receipts.jsonl")
    e.add_argument("--limit", type=int, default=10_000)
    e.set_defaults(func=_cmd_ledger_export)

    d = sub.add_parser("demo", help="demo helpers")
    dsub = d.add_subparsers(dest="demo_cmd", required=True)
    s = dsub.add_parser("run", help="walk the PRD demo script against a running gateway")
    s.add_argument("--sentinel-url", default="http://127.0.0.1:8088")
    s.set_defaults(func=_cmd_demo_run)
    s = dsub.add_parser("seed-policies", help="generate demo policy PDFs")
    s.add_argument("--out-dir", default="demo_policies")
    s.set_defaults(func=_cmd_demo_seed_policies)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    raise SystemExit(main())
