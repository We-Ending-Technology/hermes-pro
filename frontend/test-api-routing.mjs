import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const main = readFileSync(new URL("./src/main.jsx", import.meta.url), "utf8");
const api = readFileSync(new URL("./src/api.js", import.meta.url), "utf8");

assert.match(main, /import\s*\{\s*call\s*,\s*diagnose\s*\}\s*from\s*["']\.\/api\.js["']/,
  "main.jsx must use the resilient API client from src/api.js");
assert.doesNotMatch(main, /const\s+call\s*=\s*async\s*\(/,
  "main.jsx must not define its own fetch client");
assert.match(api, /hermes-pro-api-virginia\.onrender\.com/,
  "production API default must be colocated with the Virginia PostgreSQL database");

console.log("API routing regression test passed");
