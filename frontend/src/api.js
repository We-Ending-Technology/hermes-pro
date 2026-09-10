const DIRECT_API = import.meta.env.VITE_API_URL || "https://hermes-pro-api-m7wd.onrender.com";
const PROXY_API = "";

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

export async function call(path, options = {}) {
  const bases = import.meta.env.DEV ? [DIRECT_API] : [PROXY_API, DIRECT_API];
  let lastError;
  for (const base of bases) {
    try { return await request(base, path, options); }
    catch (error) { lastError = error; }
  }
  throw new Error(`Backend indisponível: ${lastError?.message || "falha de conexão"}`);
}

export async function diagnose() {
  const checks = [];
  const started = Date.now();
  const candidates = import.meta.env.DEV ? [{ label: "Render API", base: DIRECT_API }] : [
    { label: "Vercel proxy", base: PROXY_API },
    { label: "Render API", base: DIRECT_API },
  ];
  for (const candidate of candidates) {
    const t = Date.now();
    try {
      const health = await request(candidate.base, "/health");
      checks.push({ name: candidate.label, status: "online", latency_ms: Date.now() - t, message: health.service || "API online" });
      if (candidate.label === "Render API") {
        try {
          const ready = await request(candidate.base, "/ready");
          checks.push(...(ready.checks || []).map(x => ({ name: x.name, status: x.configured ? "ready" : "not_configured", latency_ms: Date.now() - t, message: x.message })));
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
