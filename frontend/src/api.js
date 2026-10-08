const DIRECT_API = import.meta.env.VITE_API_URL || "https://hermes-pro-api-m7wd.onrender.com";
const PROXY_API = "";

async function request(base, path, options = {}) {
  const response = await fetch(base + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const text = await response.text();
  let body = {};
  try { body = text ? JSON.parse(text) : {}; } catch { body = { detail: text }; }
  if (!response.ok) {
    const error = new Error(body.detail || ("HTTP " + response.status));
    error.status = response.status;
    error.base = base || "proxy";
    throw error;
  }
  return body;
}
export async function call(path, options = {}) {
  const bases = import.meta.env.DEV ? [DIRECT_API] : [PROXY_API, DIRECT_API];
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
    { label: "Vercel proxy", base: PROXY_API }, { label: "Render API", base: DIRECT_API },
  ];
  for (const candidate of candidates) {
    const t = Date.now();
    try {
      const health = await request(candidate.base, "/health");
      checks.push({ name: candidate.label, status: "online", latency_ms: Date.now() - t, message: health.service || "API online" });
      if (candidate.label === "Render API") {
        try {
          const ready = await request(candidate.base, "/api/v1/readiness");
          const blocking = new Set(ready.blocking_integrations || []);
          for (const item of ready.integrations || []) {
            const status = item.status || "not_configured";
            checks.push({ name: item.name, status: (status === "connected" || status === "configured" || status === "ready") ? "ready" : blocking.has(item.name) ? "not_configured" : "optional", latency_ms: Date.now() - t, message: item.message || status });
          }
          checks.push({ name: "Readiness", status: ready.status === "ready_with_credentials" ? "ready" : "optional", latency_ms: Date.now() - t, message: ready.next_step || "Estado de prontidão retornado pelo backend." });
        } catch (error) {
          checks.push({ name: "Readiness", status: "error", latency_ms: Date.now() - t, message: error.message });
        }
      }
    } catch (error) {
      checks.push({ name: candidate.label, status: "offline", latency_ms: Date.now() - t, message: error.message });
    }
  }
  return { checks, elapsed_ms: Date.now() - started, timestamp: new Date().toISOString() };
}
