const DIRECT_API = import.meta.env.VITE_API_URL || "https://hermes-pro-api-commercial.onrender.com";
const PROXY_API = "";
let rejectedToken = false;

function getAdminToken() {
  try {
    const saved = sessionStorage.getItem("hermes_admin_api_token");
    if (saved && !rejectedToken) return saved;
    if (rejectedToken && saved) sessionStorage.removeItem("hermes_admin_api_token");
    rejectedToken = false;
    const entered = window.prompt("Acesso privado do Hermes: cole o HERMES_API_TOKEN já configurado no Render. Isso não é uma nova chave de IA nem do Supabase.");
    if (!entered || !entered.trim()) return "";
    sessionStorage.setItem("hermes_admin_api_token", entered.trim());
    return entered.trim();
  } catch {
    return "";
  }
}

async function request(base, path, options = {}, authRetry = true) {
  const headers = { ...(options.headers || {}) };
  // Avoid unnecessary CORS preflights on GET/HEAD health and read-only calls.
  if (options.body !== undefined && options.body !== null && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  if (path.startsWith("/api/v1/") && path !== "/api/v1/webhooks/hotmart") {
    const token = getAdminToken();
    if (!token) throw new Error("Acesso privado não informado. Atualize a página e cole o HERMES_API_TOKEN já configurado no Render.");
    headers["X-Hermes-API-Key"] = token;
  }
  const response = await fetch(base + path, { ...options, headers });
  const text = await response.text();
  let body = {};
  try { body = text ? JSON.parse(text) : {}; } catch { body = { detail: text }; }
  if (response.status === 401 && path.startsWith("/api/v1/") && path !== "/api/v1/webhooks/hotmart" && authRetry) {
    try { sessionStorage.removeItem("hermes_admin_api_token"); } catch {}
    rejectedToken = true;
    return request(base, path, options, false);
  }
  if (!response.ok) {
    const error = new Error(body.detail || ("HTTP " + response.status));
    error.status = response.status;
    error.base = base || "proxy";
    throw error;
  }
  return body;
}

export async function call(path, options = {}) {
  const bases = import.meta.env.DEV ? [DIRECT_API] : [PROXY_API, DIRECT_API].filter(Boolean);
  let lastError;
  for (const base of bases) {
    try { return await request(base, path, options); } catch (error) { lastError = error; }
  }
  throw new Error("Backend indisponível: " + (lastError?.message || "falha de conexão"));
}

export async function diagnose() {
  const checks = [];
  const started = Date.now();
  const candidates = import.meta.env.DEV ? [{ label: "Render API", base: DIRECT_API }] : [
    { label: "Render API", base: DIRECT_API },
  ];
  for (const candidate of candidates) {
    const t = Date.now();
    try {
      const health = await request(candidate.base, "/");
      checks.push({ name: candidate.label, status: "online", latency_ms: Date.now() - t, message: health.service || "API online" });
      try {
        const ready = await request(candidate.base, "/ready");
        const blocking = new Set(ready.blocking_integrations || []);
        for (const item of ready.integrations || ready.checks || []) {
          const status = item.status || "not_configured";
          checks.push({ name: item.name, status: (status === "connected" || status === "configured" || status === "ready") ? "ready" : blocking.has(item.name) ? "not_configured" : "optional", latency_ms: Date.now() - t, message: item.message || status });
        }
        checks.push({ name: "Readiness", status: ready.status === "ready" || ready.status === "ready_with_credentials" ? "ready" : "optional", latency_ms: Date.now() - t, message: ready.next_step || "Estado de prontidão retornado pelo backend." });
      } catch (error) {
        checks.push({ name: "Readiness", status: "error", latency_ms: Date.now() - t, message: error.message });
      }
    } catch (error) {
      checks.push({ name: candidate.label, status: "offline", latency_ms: Date.now() - t, message: error.message });
    }
  }
  return { checks, elapsed_ms: Date.now() - started, timestamp: new Date().toISOString() };
}
