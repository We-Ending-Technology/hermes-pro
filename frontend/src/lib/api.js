const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout ?? 12000);
  try {
    const response = await fetch(`${API_URL}${path}`, { ...options, signal: controller.signal, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || body.message || `HTTP ${response.status}`);
    return body;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Tempo limite excedido ao falar com a API.");
    throw error;
  } finally { clearTimeout(timeout); }
}

export const api = {
  dashboard: () => request("/api/v1/dashboard"),
  products: () => request("/api/v1/products"),
  createProduct: (payload) => request("/api/v1/products", { method: "POST", body: JSON.stringify(payload) }),
  product: (id) => request(`/api/v1/products/${id}`),
  job: (id) => request(`/api/v1/jobs/${id}`),
  radar: (payload) => request("/api/v1/radar", payload ? { method: "POST", body: JSON.stringify(payload) } : {}),
  sales: () => request("/api/v1/sales"),
  analytics: () => request("/api/v1/analytics"),
  agents: () => request("/api/v1/agents"),
  integrations: () => request("/api/v1/integrations"),
};
