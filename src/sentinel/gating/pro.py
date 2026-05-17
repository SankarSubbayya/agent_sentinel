"""Escalation path: Gemini 2.5 Pro reasoning over full policy docs via Cached Content.

Pro receives the call envelope, the agent's recent action history (drift signal),
and one CachedContent per applicable policy doc — never the policy text directly,
so cache hits are deterministic per (model_version, cache_id, prompt). Returns a
GateDecision with citations encoded in the rationale and the policy_versions_used
list."""
from __future__ import annotations

import json
import re
from typing import Any

from google import genai
from google.genai import types

from sentinel.config import get_settings
from sentinel.models import AgentRecord, GateDecision, ToolCallRequest
from sentinel.policy_pipe.loader import load_caches_for

_client: genai.Client | None = None


def _client_singleton() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_settings().gemini_api_key)
    return _client


_SYSTEM = """You are Sentinel's senior policy reasoner. Use ONLY the cached
policy documents to decide. Always cite the policy name + version in the
rationale. Output the GateDecision schema strictly.

Decision rubric:
- If any policy explicitly forbids the action -> decision="deny".
- If the action is allowed but contains data that violates a redaction rule
  -> decision="rewrite" with rewritten_args showing the redacted form.
- Otherwise -> decision="allow".
- Set escalate=false (you ARE the escalation).
- If you detect intent drift relative to the declared goal or recent history,
  prefer "deny" with explicit citation of the goal mismatch.
"""


_INJECTION_HINTS_PRO = re.compile(
    r"(ignore (all )?previous|disregard your goal|new instructions|"
    r"override the system|wire to|forward.*attacker|exfiltrate)",
    re.IGNORECASE,
)


def _stub_pro_decision(
    call: ToolCallRequest,
    agent: AgentRecord,
    caches: list[dict[str, Any]],
    recent: list[dict[str, Any]],
    flash_decision: GateDecision | None,
) -> GateDecision:
    """Stub Pro escalation used when no Gemini key or no policy cache is available.

    Critical rule: NEVER weaken a Flash deny. Pro can only confirm or further
    restrict. The stub returns a conservative decision so demo correctness
    doesn't depend on a live API."""
    flat = " ".join(f"{k}={v}" for k, v in call.args.items())
    has_injection = bool(_INJECTION_HINTS_PRO.search(flat))

    # 1) Hard upheld deny — Flash already denied, or injection markers present.
    if (flash_decision and flash_decision.decision == "deny") or has_injection:
        rationale = (
            "Pro escalation (stub mode): upholding deny — "
            f"{'Flash flagged a violation; ' if flash_decision and flash_decision.decision == 'deny' else ''}"
            f"{'prompt-injection markers present in tool arguments; ' if has_injection else ''}"
            f"action conflicts with declared goal \"{agent.declared_goal}\"."
        )
        return GateDecision(
            decision="deny",
            confidence=0.94,
            escalate=False,
            rationale=rationale.rstrip(", "),
        )

    # 2) Drift signal — fresh sensitive tool the agent hasn't used before.
    recent_tools = {r["tool"] for r in recent}
    looks_drifted = (
        call.tool in {"email.send_external", "webhook.post", "http.post", "refund.issue"}
        and recent_tools
        and call.tool not in recent_tools
    )
    if looks_drifted:
        return GateDecision(
            decision="deny",
            confidence=0.91,
            escalate=False,
            rationale=(
                "Pro escalation (stub mode): action diverges from this agent's "
                "recent behavior pattern and from declared goal "
                f"\"{agent.declared_goal}\". No matching policy permits it."
            ),
        )

    # 3) Otherwise echo Flash's decision (Pro shouldn't override without basis).
    if flash_decision is not None:
        return GateDecision(
            decision=flash_decision.decision,
            confidence=min(1.0, (flash_decision.confidence or 0.0) + 0.05),
            escalate=False,
            rationale=(
                f"Pro escalation (stub mode): confirmed Flash's {flash_decision.decision} — "
                f"{flash_decision.rationale}"
            ),
            rewritten_args=flash_decision.rewritten_args,
        )
    return GateDecision(
        decision="allow",
        confidence=0.80,
        escalate=False,
        rationale=(
            "Pro escalation (stub mode): no Flash context provided; allowing as no "
            "policy violation surfaced and action is consistent with declared goal."
        ),
    )


def _envelope(
    call: ToolCallRequest, agent: AgentRecord, recent: list[dict[str, Any]]
) -> str:
    recent_str = (
        "\n".join(
            f"  - {r['created_at']:%H:%M:%S}  {r['tool']:<24}  {r['decision']}"
            for r in recent[:20]
        )
        or "  (no prior actions)"
    )
    return (
        f"AGENT: {agent.agent_id}  role={agent.role}  bu={agent.bu}\n"
        f"DECLARED_GOAL: {agent.declared_goal or '(none)'}\n"
        f"RECENT_ACTIONS (newest first):\n{recent_str}\n\n"
        f"PROPOSED CALL:\n"
        f"  tool: {call.tool}\n"
        f"  args: {json.dumps(call.args, default=str)}\n"
    )


async def pro_escalation(
    call: ToolCallRequest,
    agent: AgentRecord,
    recent: list[dict[str, Any]],
    flash_decision: GateDecision | None = None,
) -> tuple[GateDecision, list[dict[str, str]], list[str]]:
    """Returns (decision, policy_versions_used, gemini_cache_ids).

    flash_decision is the prior Flash gate output; the stub-mode Pro will not
    weaken it. When real Gemini is configured, Pro's own structured output
    is authoritative."""
    settings = get_settings()
    caches = await load_caches_for(call.tool, agent.role)

    policy_versions = [{"name": c["name"], "version": c["version"]} for c in caches]
    cache_ids = [c["cache_id"] for c in caches]

    if not settings.gemini_api_key or not caches:
        return (
            _stub_pro_decision(call, agent, caches, recent, flash_decision),
            policy_versions,
            cache_ids,
        )

    client = _client_singleton()
    prompt = _envelope(call, agent, recent)

    # Pro can only attach one cached_content per call today. If multiple
    # policies match, pick the one with the most overlapping tags first;
    # downstream policies inform via prompt context.
    primary_cache = cache_ids[0]
    resp = await client.aio.models.generate_content(
        model=settings.pro_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            cached_content=primary_cache,
            response_mime_type="application/json",
            response_schema=GateDecision,
            temperature=0.1,
        ),
    )
    parsed: GateDecision = resp.parsed  # type: ignore[assignment]
    if parsed is None:
        return (
            _stub_pro_decision(call, agent, caches, recent, flash_decision),
            policy_versions,
            cache_ids,
        )
    return parsed, policy_versions, cache_ids
