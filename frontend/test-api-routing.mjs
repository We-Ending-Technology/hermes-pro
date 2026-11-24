import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const main = readFileSync(new URL("./src/main.jsx", import.meta.url), "utf8");
const api = readFileSync(new URL("./src/api.js", import.meta.url), "utf8");

assert.match(main, /import\s*\{\s*call\s*,\s*diagnose\s*\}\s*from\s*["']\.\/api\.js["']/, 
  "main.jsx must use the resilient API client from src/api.js");
assert.doesNotMatch(main, /const\s+call\s*=\s*async\s*\(/,
  "main.jsx must not define its own fetch client");

assert.doesNotMatch(main, /apiAccess/,
  "main.jsx must not reference the removed manual API-key access state");
assert.match(api, /request\(candidate\.base, "\/ready"\)/,
  "diagnostics must call the backend readiness endpoint");
assert.doesNotMatch(api, /\/api\/v1\/readiness/,
  "diagnostics must not call a nonexistent readiness route");
assert.match(api, /VITE_API_PROXY/,
  "a proxy must be explicitly configured before it is used");

console.log("API routing regression test passed");
