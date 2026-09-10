import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const main = readFileSync(new URL("./src/main.jsx", import.meta.url), "utf8");

assert.match(main, /import\s*\{\s*call\s*\}\s*from\s*["']\.\/api\.js["']/,
  "main.jsx must use the resilient API client from src/api.js");
assert.doesNotMatch(main, /const\s+call\s*=\s*async\s*\(/,
  "main.jsx must not define its own fetch client");

console.log("API routing regression test passed");
