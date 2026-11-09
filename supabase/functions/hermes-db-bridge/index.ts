import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
const secretKeys = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}");
const adminKey = secretKeys.default ?? Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

function hex(bytes: Uint8Array): string {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return hex(new Uint8Array(digest));
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function privilegedHeaders(): Headers {
  const headers = new Headers({ apikey: adminKey, accept: "application/json" });
  // Legacy service_role keys are JWTs. New sb_secret_ keys must be sent only as apikey.
  if (adminKey.startsWith("eyJ")) headers.set("Authorization", `Bearer ${adminKey}`);
  return headers;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204 });
  if (!supabaseUrl || !adminKey) {
    return Response.json({ error: "privileged_database_runtime_unavailable" }, { status: 503 });
  }

  const incoming = req.headers.get("x-hermes-bridge-key") ?? "";
  if (!incoming) return Response.json({ error: "unauthorized" }, { status: 401 });

  const lookup = await fetch(
    `${supabaseUrl.replace(/\/$/, "")}/rest/v1/hermes_bridge_secret?select=secret_hash&id=eq.true`,
    { headers: privilegedHeaders() },
  );
  if (!lookup.ok) return Response.json({ error: "bridge_not_configured" }, { status: 503 });
  const rows = await lookup.json();
  const storedHash = Array.isArray(rows) ? rows[0]?.secret_hash : null;
  if (!storedHash) return Response.json({ error: "bridge_not_configured" }, { status: 503 });

  const suppliedHash = await sha256(incoming);
  if (!constantTimeEqual(suppliedHash, storedHash)) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  const url = new URL(req.url);
  const segments = url.pathname.split("/").filter(Boolean);
  const functionIndex = segments.indexOf("hermes-db-bridge");
  const table = functionIndex >= 0 ? segments.slice(functionIndex + 1).join("/") : "";
  if (!/^[a-z][a-z0-9_]*$/.test(table) || table === "hermes_bridge_secret") {
    return Response.json({ error: "invalid_table" }, { status: 404 });
  }
  if (!["GET", "POST", "PATCH", "DELETE"].includes(req.method)) {
    return Response.json({ error: "method_not_allowed" }, { status: 405 });
  }

  const headers = privilegedHeaders();
  headers.set("Content-Type", req.headers.get("content-type") ?? "application/json");
  for (const name of ["prefer", "accept", "range", "range-unit"]) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }

  const target = `${supabaseUrl.replace(/\/$/, "")}/rest/v1/${table}${url.search}`;
  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body: ["GET", "DELETE"].includes(req.method) ? undefined : await req.text(),
  });

  const responseHeaders = new Headers();
  for (const name of ["content-type", "content-range", "content-location", "preference-applied", "location"]) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
});