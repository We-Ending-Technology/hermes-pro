import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { formatCurrency, navItems, statusTone } from "./ui.js";

test("command center navigation exposes the core operating areas", () => {
  assert.deepEqual(navItems.slice(0, 5), ["Início", "Radar", "Fábrica", "Produtos", "Vendas"]);
});

test("command center hides the old English Sales orbit label", () => {
  const styles = readFileSync(new URL("../workspace.css", import.meta.url), "utf8");
  assert.match(styles, /\.orbit-label\.l3\{[^}]*display:none/);
});

test("currency formatter renders Brazilian money", () => {
  assert.equal(formatCurrency(129.9), "R$ 129,90");
});

test("status tone maps known states to stable UI semantics", () => {
  assert.equal(statusTone("completed"), "success");
  assert.equal(statusTone("running"), "active");
  assert.equal(statusTone("failed"), "danger");
  assert.equal(statusTone("unknown"), "neutral");
});


test("private API access token is memory-only and can be cleared", async () => {
  const { setAdminToken, clearAdminToken, hasAdminToken } = await import("../api.js");
  clearAdminToken();
  assert.equal(hasAdminToken(), false);
  setAdminToken("test-key");
  assert.equal(hasAdminToken(), true);
  clearAdminToken();
  assert.equal(hasAdminToken(), false);
});

test("frontend authentication never opens a blocking browser prompt", () => {
  const api = readFileSync(new URL("../api.js", import.meta.url), "utf8");
  const app = readFileSync(new URL("../main.jsx", import.meta.url), "utf8");
  assert.doesNotMatch(api + app, /window\\.prompt\\s*\\(/);
  assert.match(api, /X-Hermes-API-Key/);
});
