const ALLOWED_METHODS = new Set(["GET", "POST", "PATCH", "PUT", "DELETE"]);
const PUBLIC_PATHS = new Set(["/", "/health", "/ready", "/time"]);

export const config = {
  api: { bodyParser: false },
  maxDuration: 60,
};

async function readRawBody(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  const method = req.method || "";

  if (!ALLOWED_METHODS.has(method)) {
    res.setHeader("Allow", [...ALLOWED_METHODS].join(", "));
    return res.status(405).json({ detail: "Method not allowed." });
  }

  const originValue = process.env.HERMES_API_ORIGIN || "";
  const apiKey = process.env.HERMES_API_KEY || "";
  if (!originValue || !apiKey) {
    return res.status(503).json({ detail: "Private API proxy is not configured." });
  }

  let origin;
  try {
    origin = new URL(originValue);
  } catch {
    return res.status(503).json({ detail: "Private API upstream is invalid." });
  }
  if (origin.protocol !== "https:" || origin.hostname !== "hermes-pro-api-commercial.onrender.com") {
    return res.status(503).json({ detail: "Private API upstream is not allowed." });
  }

  const rawPath = req.query && req.query.path;
  let requestedPath = Array.isArray(rawPath) ? rawPath.join("/") : String(rawPath || "");
  requestedPath = requestedPath.trim();
  while (requestedPath.startsWith("/")) requestedPath = requestedPath.slice(1);

  let target;
  try {
    target = new URL(requestedPath, origin);
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
  if (method !== "GET" && method !== "HEAD") {
    try {
      body = await readRawBody(req);
    } catch {
      return res.status(400).json({ detail: "Could not read request body." });
    }
  }

  try {
    const upstream = await fetch(target.toString(), {
      method,
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
