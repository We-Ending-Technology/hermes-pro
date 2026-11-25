import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const main = readFileSync(new URL("./src/main.jsx", import.meta.url), "utf8");
const api = readFileSync(new URL("./src/api.js", import.meta.url), "utf8");

assert.match(main, /import\\s*\\{\\s*call\\s*,\\s*diagnose\\s*\\}\\s*from\\s*["']\\.\\/api\\.js["']/,
  "main.jsx must use the resilient API client from src/api.js");
assert.doesNotMatch(main, /const\\s+call\\s*=\\s*async\\s*\\(/,
  "main.jsx must not define its own fetch client");
assert.doesNotMatch(main, /apiAccess/,
  "main.jsx must not reference the removed manual API-key access state");
assert.match(api, /request\\(candidate\\.base, "\\/ready"\\)/,
  "diagnostics must call the backend readiness endpoint");
assert.doesNotMatch(api, /\\/api\\/v1\\/readiness/,
  "diagnostics must not call a nonexistent readiness route");
assert.match(api, /import\\.meta\\.env\\.PROD \\? "\\/api\\/hermes\\?path="/,
  "production must default to the same-origin private proxy");
assert.match(api, /encodeURIComponent\\(path\\.replace/,
  "the browser must encode backend paths as one proxy query parameter");
assert.match(api, /if \\(PROXY_API\\) return \\[\\{ label: "Proxy privado"/,
  "the browser must not fall back to the public Render API when proxying is enabled");
assert.doesNotMatch(api, /X-Hermes-API-Key/,
  "the private API key must never be shipped in browser code");

const proxy = readFileSync(new URL("./api/hermes.js", import.meta.url), "utf8");
assert.match(proxy, /process\\.env\\.HERMES_API_KEY/,
  "the server-side proxy must read the key from server environment variables");
assert.match(proxy, /X-Hermes-API-Key/,
  "the server-side proxy must attach the private API key upstream");
assert.match(proxy, /hermes-pro-api-commercial\\.onrender\\.com/,
  "the proxy must restrict outbound requests to the registered Render API");
assert.match(proxy, /new URL\\(/,
  "the proxy must parse routes safely before forwarding requests");

console.log("API routing regression test passed");
