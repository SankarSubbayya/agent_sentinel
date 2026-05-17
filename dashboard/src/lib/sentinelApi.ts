// Sentinel backend client. All fetches are no-credentials JSON, CORS-friendly.

export const SENTINEL_URL =
  process.env.NEXT_PUBLIC_SENTINEL_URL || "http://127.0.0.1:8088";

export type Decision = "allow" | "deny" | "rewrite";
export type DecidedBy = "static" | "flash" | "pro" | string;

export interface Receipt {
  receipt_id: string;
  agent_id: string;
  bu: string;
  tool: string;
  decision: Decision;
  decided_by: DecidedBy;
  escalated: boolean;
  rationale: string;
  latency_ms: number;
  created_at: string;
  policy_versions_used?: Array<{ name: string; version: string }>;
}

export interface ReceiptsResponse {
  receipts: Receipt[];
  count: number;
}

export interface ToolCallRequest {
  agent_id: string;
  session_id: string;
  tool: string;
  args: Record<string, unknown>;
}

export interface ToolCallResponse {
  decision: Decision;
  receipt_id: string;
  rationale: string;
  rewritten_args?: Record<string, unknown> | null;
  cost_usd: number;
  latency_ms: number;
}

export interface CostRow {
  bu: string;
  calls: number;
  base_usd: number;
  gemini_usd: number;
  total_usd: number;
}

export interface CostRollupResponse {
  days: number;
  rows: CostRow[];
}

export interface PolicyDoc {
  id: string;
  name: string;
  version: string;
  effective_date: string;
  cache_id?: string | null;
  domain_tags?: string[];
}

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${SENTINEL_URL}${path}`, {
    ...init,
    credentials: "omit",
    cache: "no-store",
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    throw new Error(`GET ${path} -> ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${SENTINEL_URL}${path}`, {
    method: "POST",
    credentials: "omit",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`POST ${path} -> ${res.status} ${res.statusText} ${txt}`);
  }
  return (await res.json()) as T;
}

export async function healthcheck(): Promise<{ status: string } | null> {
  try {
    return await get<{ status: string }>("/healthz");
  } catch {
    return null;
  }
}

export interface ReceiptsFilter {
  agent_id?: string;
  bu?: string;
  tool?: string;
  decision?: Decision | "";
  limit?: number;
}

export async function getReceipts(
  filter: ReceiptsFilter = {}
): Promise<ReceiptsResponse> {
  const qs = new URLSearchParams();
  if (filter.agent_id) qs.set("agent_id", filter.agent_id);
  if (filter.bu) qs.set("bu", filter.bu);
  if (filter.tool) qs.set("tool", filter.tool);
  if (filter.decision) qs.set("decision", filter.decision);
  if (filter.limit) qs.set("limit", String(filter.limit));
  const q = qs.toString();
  return get<ReceiptsResponse>(`/v1/receipts${q ? `?${q}` : ""}`);
}

export async function getCostRollup(days = 7): Promise<CostRollupResponse> {
  return get<CostRollupResponse>(`/v1/cost/rollup?days=${days}`);
}

export async function postToolCall(
  req: ToolCallRequest
): Promise<ToolCallResponse> {
  return postJson<ToolCallResponse>("/v1/tools/call", req);
}

// Placeholder — endpoint may not exist yet; caller handles failure.
export async function getPolicies(): Promise<{ policies: PolicyDoc[] }> {
  return get<{ policies: PolicyDoc[] }>("/v1/policies");
}

// Agent runner — drive an LLM agent against a brief; every tool call
// flows through the same gating pipeline as POST /v1/tools/call.
export interface AgentStep {
  step: number;
  kind: "thought" | "tool_call" | "final";
  thought?: string | null;
  tool?: string | null;
  args?: Record<string, unknown>;
  decision?: Decision | null;
  decided_by?: DecidedBy | null;
  rationale?: string | null;
  receipt_id?: string | null;
  latency_ms?: number | null;
  cost_usd?: number | null;
  tool_result?: string | null;
  final_message?: string | null;
  escalated?: boolean;
  policy_versions_used?: Array<{ name: string; version: string }>;
}

export interface AgentRunResponse {
  agent_id: string;
  session_id: string;
  brief: string;
  mode: "live" | "stub";
  final_message: string | null;
  total_cost_usd: number;
  steps: AgentStep[];
}

export async function postAgentRun(
  agent_id: string,
  brief: string,
  max_steps = 6
): Promise<AgentRunResponse> {
  return postJson<AgentRunResponse>("/v1/agents/run", {
    agent_id,
    brief,
    max_steps,
  });
}

export async function uploadPolicy(
  file: File
): Promise<{ ok: boolean; message?: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${SENTINEL_URL}/v1/policies/upload`, {
    method: "POST",
    credentials: "omit",
    body: form,
  });
  if (!res.ok) {
    return { ok: false, message: `${res.status} ${res.statusText}` };
  }
  try {
    const json = (await res.json()) as Record<string, unknown>;
    return { ok: true, message: JSON.stringify(json) };
  } catch {
    return { ok: true };
  }
}
