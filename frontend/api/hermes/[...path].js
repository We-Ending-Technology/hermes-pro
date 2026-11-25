const ALLOWED_METHODS = new Set(["GET", "POST", "PATCH", "PUT", "DELETE"]);
const PUBLIC_PATHS = new Set(["/", "/health", "/ready", "/time"]);
const API_PREFIX = "/api/hermes";

export const config = { maxDuration: 60 };

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");

  if (!ALLOWED_METHODS.has(req.method || "")) {
    res.setHeader("Allow", [...ALLOWED_METHODS].join(", "));
    return res.status(405).json({ detail: "Method not allowed." });
  }

  const apiOrigin = (process.env.HERMES_API_ORIGIN || "").replace(/\/+$/, "");
  const apiKey = process.env.HERMES_API_KEY || "";
  if (!apiOrigin || !apiKey) {
    return res.status(503).json({ detail: "Private API proxy is not configured." });
  }

  let incoming;
  try {
    incoming = new URL(req.url || "/", "http://localhost");
  } catch {
    return res.status(400).json({ detail: "Invalid request URL." });
  }

  if (!incoming.pathname.startsWith(API_PREFIX + "/")) {
    return res.status(404).json({ detail: "Not found." });
  }

  const upstreamPath = incoming.pathname.slice(API_PREFIX.length);
  const allowedPath = PUBLIC_PATHS.has(upstreamPath) || upstreamPath.startsWith("/api/v1/");
  if (!allowedPath) {
    return res.status(404).json({ detail: "Not found." });
  }

  const headers = {
    "X-Hermes-API-Key": apiKey,
    "Accept": req.headers.accept || "application/json",
  };
  if (req.headers["content-type"]) {
    headers["Content-Type"] = req.headers["content-type"];
  }

  let body;
  if (!["GET", "HEAD"].includes(req.method || "")) {
    if (typeof req.body === "string") body = req.body;
    else if (req.body !== undefined && req.body !== null) body = JSON.stringify(req.body);
  }

  try {
    const upstream = await fetch(`${apiOrigin}${upstreamPath}${incoming.search}`, {
      method: req.method,
      headers,
      body,
      redirect: "manual",
      cache: "no-store",
    });
    const payload = await upstream.text();
    res.status(upstream.status);
    res.setHeader("Content-Type", upstream.headers.get("content-type") || "application/json");
    return res.send(payload);
  } catch {
    return res.status(502).json({ detail: "Private API upstream is unavailable." });
  }
}
