const ALLOWED_METHODS = new Set(["GET", "POST", "PATCH", "PUT", "DELETE"]);
const PUBLIC_PATHS = new Set(["/", "/health", "/ready", "/time"]);
export const config = { maxDuration: 60 };

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");

  if (!ALLOWED_METHODS.has(req.method || "")) {
    res.setHeader("Allow", [...ALLOWED_METHODS].join(", "));
    return res.status(405).json({ detail: "Method not allowed." });
  }

  const apiOrigin = (process.env.HERMES_API_ORIGIN || "").replace(/\\/+$/, "");
  const apiKey = process.env.HERMES_API_KEY || "";
  if (!apiOrigin || !apiKey) {
    return res.status(503).json({ detail: "Private API proxy is not configured." });
  }

  let origin;
  try {
    origin = new URL(apiOrigin);
  } catch {
    return res.status(503).json({ detail: "Private API upstream is invalid." });
  }
  if (origin.protocol !== "https:" || origin.hostname !== "hermes-pro-api-commercial.onrender.com") {
    return res.status(503).json({ detail: "Private API upstream is not allowed." });
  }

  const rawPath = req.query?.path;
  const requestedPath = Array.isArray(rawPath) ? rawPath.join("/") : String(rawPath || "");
  const upstreamPath = "/" + requestedPath.replace(/^\\/+/, "");
  let target;
  try {
    target = new URL(upstreamPath, origin);
  } catch {
    return res.status(400).json({ detail: "Invalid upstream path." });
  }
  const allowedPath = PUBLIC_PATHS.has(target.pathname) || target.pathname.startsWith("/api/v1/");
  if (!allowedPath || target.origin !== origin.origin) {
    return res.status(404).json({ detail: "Not found." });
  }

  const headers = {
    "X-Hermes-API-Key": apiKey,
    "Accept": req.headers.accept || "application/json",
  };
  if (req.headers["content-type"]) headers["Content-Type"] = req.headers["content-type"];

  let body;
  if (!["GET", "HEAD"].includes(req.method || "")) {
    if (typeof req.body === "string") body = req.body;
    else if (req.body !== undefined && req.body !== null) body = JSON.stringify(req.body);
  }

  try {
    const upstream = await fetch(target.toString(), {
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
