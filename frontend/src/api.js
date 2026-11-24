const DIRECT_API = (import.meta.env.VITE_API_URL || "https://hermes-pro-api-commercial.onrender.com").replace(/\/+$/, "");
const PROXY_API = (import.meta.env.VITE_API_PROXY || "").replace(/\/+$/, "");

async function request(base, path, options = {}) {
  const response = await fetch(`${base}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const text = await response.text();
  let body = {};
  try { body = text ? JSON.parse(text) : {}; } catch { body = { detail: text }; }
  if (!response.ok) {
    const error = new Error(body.detail || `HTTP ${response.status}`);
    error.status = response.status;
    error.base = base || "proxy";
    throw error;
  }
  return body;
}

function apiCandidates() {
  const candidates = [];
  if (PROXY_API) candidates.push({ label: "Proxy", base: PROXY_API });
  candidates.push({ label: "Render API", base: DIRECT_API });
  return candidates;
}

export async function call(path, options = {}) {
  let lastError;
  for (const candidate of apiCandidates()) {
    try { return await request(candidate.base, path, options); }
    catch (error) { lastError = error; }
  }
  throw new Error(`Backend indisponível: ${lastError?.message || "falha de conexão"}`);
}

export async function diagnose() {
  const checks = [];
  const started = Date.now();
  for (const candidate of apiCandidates()) {
    const t = Date.now();
    try {
      const health = await request(candidate.base, "/health");
      checks.push({
        name: candidate.label,
        status: health?.status === "ok" ? "online" : "error",
        latency_ms: Date.now() - t,
        message: health.service || "API online",
      });
      if (candidate.label !== "Render API") continue;

      try {
        const ready = await request(candidate.base, "/ready");
        checks.push({
          name: "Banco de dados",
          status: ready?.checks?.database === "ok" ? "ready" : "error",
          latency_ms: Date.now() - t,
          message: ready?.checks?.database === "ok" ? "Supabase respondeu" : "Banco indisponível",
        });
      } catch (error) {
        checks.push({ name: "Banco de dados", status: "error", latency_ms: Date.now() - t, message: error.message });
      }

      try {
        const agents = await request(candidate.base, "/api/v1/agents/status");
        checks.push({
          name: "Hermes Chefe",
          status: agents?.chief === "ready" ? "ready" : "error",
          latency_ms: Date.now() - t,
          message: agents?.chief || "Estado do Chefe indisponível",
        });
        checks.push({
          name: "Provedor de IA",
          status: agents?.ai_provider_status === "ready" ? "ready" : "error",
          latency_ms: Date.now() - t,
          message: agents?.ai_provider_last_error || `${agents?.ai_provider || "IA"}: ${agents?.ai_provider_status || "sem estado"}`,
        });
        checks.push({
          name: "Orçamento de IA",
          status: agents?.ai_budget?.allowed === true ? "ready" : "error",
          latency_ms: Date.now() - t,
          message: agents?.ai_budget?.message || "Não foi possível confirmar a permissão de uso da IA.",
        });
        checks.push({
          name: "Fila Redis",
          status: agents?.queue_status === "ready" ? "ready" : "error",
          latency_ms: Date.now() - t,
          message: agents?.queue_status || "Estado da fila indisponível",
        });
        checks.push({
          name: "Worker",
          status: agents?.worker_status === "ready" ? "ready" : "error",
          latency_ms: Date.now() - t,
          message: agents?.worker_last_seen_at
            ? `Último heartbeat há ${agents.worker_age_seconds ?? "?"}s`
            : "Heartbeat indisponível",
        });
      } catch (error) {
        checks.push({ name: "Agentes", status: "error", latency_ms: Date.now() - t, message: error.message });
      }

      try {
        const integrations = await request(candidate.base, "/api/v1/integrations");
        for (const item of Array.isArray(integrations) ? integrations : []) {
          const status = String(item.status || "").toLowerCase();
          const level = ["connected", "configured"].includes(status)
            ? "ready"
            : ["profile_registered", "workspace_registered", "webhook_configured"].includes(status)
              ? "optional"
              : "not_configured";
          checks.push({
            name: item.name,
            status: level,
            latency_ms: Date.now() - t,
            message: item.message || status || "Sem estado",
          });
        }
      } catch (error) {
        checks.push({ name: "Integrações", status: "error", latency_ms: Date.now() - t, message: error.message });
      }
    } catch (error) {
      checks.push({ name: candidate.label, status: "offline", latency_ms: Date.now() - t, message: error.message });
    }
  }
  return { checks, elapsed_ms: Date.now() - started, timestamp: new Date().toISOString() };
}
