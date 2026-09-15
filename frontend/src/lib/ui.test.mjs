import test from "node:test";
import assert from "node:assert/strict";
import { formatCurrency, navItems, statusTone } from "./ui.js";

test("command center navigation exposes the core operating areas", () => {
  assert.deepEqual(navItems.slice(0, 5), ["Início", "Radar", "Fábrica", "Produtos", "Vendas"]);
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
