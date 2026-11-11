const DIRECT_API = import.meta.env?.VITE_API_URL || "https://hermes-pro-api-commercial.onrender.com";
const PROXY_API = "";

// The private API key exists only in this page's JavaScript memory.
let adminToken = "";
let warmupPromise = null;
export function warmApi() {
  if (!warmupPromise) warmupPromise = fetch(DIRECT_API + "/health", { cache: "no-store" }).then(r => r.ok ? r.json() : null).catch(() => null).finally(() => { warmupPromise = null; });
  return warmupPromise;
}

export function setAdminToken(value) {
  adminToken = String(value || "").trim();
}

export function clearAdminToken() {
  adminToken = "";
}

export function hasAdminToken() {
  return Boolean(adminToken);
}

function getAdminToken() {
  return adminToken;
}

async function request(base, path, options = {}) {
  const { timeoutMs = 15000, ...fetchOptions } = options;
  const headers = { ...(fetchOptions.headers || {}) };
  const needsAdminToken = path.startsWith("/api/v1/")
    && path !== "/api/v1/webhooks/hotmart";
  if (fetchOptions.body !== undefined && fetchOptions.body !== null && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  if (needsAdminToken) {
    const token = getAdminToken();
    if (!token) throw new Error("Acesso privado não informado. Digite a chave configurada em HERMES_API_KEY no Render.");
    headers["X-Hermes-API-Key"] = token;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(base + path, { ...fetchOptions, headers, signal: controller.signal });
    const text = await response.text();
    let body = {};
    try { body = text ? JSON.parse(text) : {}; } catch { body = { detail: text }; }
    if (response.status === 401 && needsAdminToken) {
      clearAdminToken();
      throw new Error("A chave de acesso foi rejeitada. Confira HERMES_API_KEY no Render e tente novamente.");
    }
    if (!response.ok) {
      const error = new Error(body.detail || ("HTTP " + response.status));
      error.status = response.status;
      error.base = base || "proxy";
      throw error;
    }
    return body;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(`Tempo limite excedido ao consultar ${path} (${Math.ceil(timeoutMs / 1000)}s).`);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export async function call(path, options = {}) {
  const bases = import.meta.env?.DEV ? [DIRECT_API] : [PROXY_API, DIRECT_API].filter(Boolean);
  let lastError;
  for (const base of bases) {
    try { return await request(base, path, options); } catch (error) { lastError = error; }
  }
  throw new Error(lastError?.message || "Falha de conexão com o backend.");
}

export async function diagnose() {
  const checks = [];
  const started = Date.now();
  const candidates = [{ label: "Render API", base: DIRECT_API }];
  for (const candidate of candidates) {
    const t = Date.now();
    try {
      const health = await request(candidate.base, "/");
      checks.push({ name: candidate.label, status: "online", latency_ms: Date.now() - t, message: health.service || "API online" });
      try {
        const ready = await request(candidate.base, "/ready");
        const blocking = new Set(ready.blocking_integrations || []);
        const rawChecks = ready.integrations || ready.checks || [];
        const normalizedChecks = Array.isArray(rawChecks)
          ? rawChecks
          : Object.entries(rawChecks).map(([name, status]) => ({ name, status, message: status }));
        for (const item of normalizedChecks) {
          const status = item.status || "not_configured";
          checks.push({ name: item.name, status: (status === "connected" || status === "configured" || status === "ready" || status === "ok") ? "ready" : blocking.has(item.name) ? "not_configured" : "optional", latency_ms: Date.now() - t, message: item.message || status });
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
