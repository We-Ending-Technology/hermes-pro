const API_URL = (import.meta.env.VITE_API_URL || "https://hermes-pro-api-commercial.onrender.com").replace(/\/$/, "");

function getApiToken() {
  try { return sessionStorage.getItem("hermes_api_token") || ""; }
  catch { return ""; }
}

async function request(path, options = {}, retryAuth = true) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout ?? 12000);
  try {
    const token = getApiToken();
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
      ...(token ? { "X-Hermes-API-Key": token } : {}),
    };
    const response = await fetch(`${API_URL}${path}`, { ...options, signal: controller.signal, headers });
    const body = await response.json().catch(() => ({}));

    if (response.status === 401 && retryAuth && !token) {
      const supplied = window.prompt("O Hermes precisa do token HERMES_API_TOKEN já configurado no Render. O token será guardado apenas nesta sessão do navegador; não o envie no chat.");
      if (supplied && supplied.trim()) {
        try { sessionStorage.setItem("hermes_api_token", supplied.trim()); } catch {}
        clearTimeout(timeout);
        return await request(path, options, false);
      }
    }
    if (response.status === 401 && token) {
      try { sessionStorage.removeItem("hermes_api_token"); } catch {}
      throw new Error("Token do Hermes recusado. Reabra a página e informe o HERMES_API_TOKEN correto.");
    }
    if (!response.ok) throw new Error(body.detail || body.message || `HTTP ${response.status}`);
    return body;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Tempo limite excedido ao falar com a API.");
    if (error instanceof TypeError && /fetch/i.test(error.message)) {
      throw new Error("Falha de conexão/CORS com a API do Hermes. Verifique a URL da API e as origens CORS.");
    }
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
  clearSessionToken: () => { try { sessionStorage.removeItem("hermes_api_token"); } catch {} },
};
