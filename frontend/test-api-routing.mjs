import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const main = readFileSync(new URL("./src/main.jsx", import.meta.url), "utf8");
const api = readFileSync(new URL("./src/api.js", import.meta.url), "utf8");
const proxy = readFileSync(new URL("./api/hermes.js", import.meta.url), "utf8");

assert.ok(main.includes("./api.js"), "main must use the shared API client");
assert.ok(!main.includes("apiAccess"), "browser must not prompt for a manual API key");
assert.ok(api.includes("/api/hermes?path="), "production must use the same-origin proxy");
assert.ok(api.includes("encodeURIComponent(route)"), "API routes must be encoded as one query value");
assert.ok(!api.includes("X-Hermes-API-Key"), "the API key must not appear in browser code");
assert.ok(proxy.includes("process.env.HERMES_API_KEY"), "the server-side function must read the secret");
assert.ok(proxy.includes('"X-Hermes-API-Key"'), "the server-side function must add the key upstream");
assert.ok(proxy.includes("bodyParser: false"), "the proxy must preserve raw request bodies");
assert.ok(proxy.includes("hermes-pro-api-commercial.onrender.com"), "the proxy must restrict the upstream host");

console.log("API routing regression test passed");
