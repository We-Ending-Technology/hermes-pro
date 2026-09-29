export const navItems = ["Início", "Radar", "Fábrica", "Produtos", "Vendas", "Analytics", "Agentes"];

export function formatCurrency(value) {
  if (value == null || Number.isNaN(Number(value))) return "R$ —";
  return Number(value).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function statusTone(status) {
  if (["completed", "ready_to_sell", "published", "online"].includes(status)) return "success";
  if (["running", "pending", "retrying", "discovered"].includes(status)) return "active";
  if (["failed", "blocked", "cancelled", "offline"].includes(status)) return "danger";
  return "neutral";
}
