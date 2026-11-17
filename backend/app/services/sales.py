from datetime import date, datetime, time, timezone
from typing import Any

from ..db.supabase import SupabaseREST


APPROVED_EVENTS = {
    "PURCHASE_APPROVED",
    "PURCHASE_COMPLETE",
    "PURCHASE_APPROVED_EVENT",
    "SUBSCRIPTION_RENEWED",
}
REVERSAL_EVENTS = {
    "PURCHASE_REFUNDED",
    "PURCHASE_CHARGEBACK",
}


class SalesService:
    def __init__(self, db: SupabaseREST):
        self.db = db

    async def summary(self, range_start: date | None = None, range_end: date | None = None) -> dict[str, Any]:
        params: dict[str, str] = {
            "select": "amount,currency,event_type,occurred_at,provider,external_id",
            "or": "(provider.eq.hotmart,provider.eq.kiwify,provider.eq.shopify)",
            "order": "occurred_at.desc",
        }
        start = datetime.combine(range_start, time.min, tzinfo=timezone.utc).isoformat() if range_start else None
        end = datetime.combine(range_end, time.max, tzinfo=timezone.utc).isoformat() if range_end else None
        if start and end:
            params["and"] = f"(occurred_at.gte.{start},occurred_at.lte.{end})"
        elif start:
            params["occurred_at"] = f"gte.{start}"
        elif end:
            params["occurred_at"] = f"lte.{end}"

        try:
            rows = await self.db.select("hermes_sales_events", params=params)
        except Exception as exc:
            return {
                "range_start": range_start,
                "range_end": range_end,
                "revenue": None,
                "orders": None,
                "ticket": None,
                "status": "error",
                "message": f"Falha ao consultar vendas reais: {exc}",
            }

        # Never add USD/EUR/etc. into a BRL total. Unknown currencies are
        # excluded too, rather than silently assuming they are BRL.
        brl_rows = [r for r in rows if str(r.get("currency") or "").upper() == "BRL"]
        excluded_currencies = sorted({
            str(r.get("currency") or "SEM_MOEDA").upper()
            for r in rows
            if str(r.get("currency") or "").upper() != "BRL"
        })

        other_approved: list[dict[str, Any]] = []
        other_reversals: list[dict[str, Any]] = []
        shopify_paid: dict[str, float] = {}
        shopify_refunded: dict[str, float] = {}

        for row in brl_rows:
            event_type = str(row.get("event_type") or "").upper()
            amount = float(row.get("amount") or 0)
            if str(row.get("provider") or "").lower() == "shopify":
                external_id = str(row.get("external_id") or "")
                if event_type in APPROVED_EVENTS and external_id.startswith("orders/paid:"):
                    order_id = external_id.split(":", 1)[1]
                    shopify_paid[order_id] = shopify_paid.get(order_id, 0.0) + amount
                elif event_type in REVERSAL_EVENTS and external_id.startswith("refunds/create:"):
                    parts = external_id.split(":")
                    if len(parts) >= 3:
                        order_id = parts[1]
                        shopify_refunded[order_id] = shopify_refunded.get(order_id, 0.0) + amount
                continue
            if event_type in APPROVED_EVENTS:
                other_approved.append(row)
            elif event_type in REVERSAL_EVENTS:
                other_reversals.append(row)

        # Shopify can emit multiple partial refunds for the same order. Group
        # by order ID so each refund reduces revenue, but not the order count
        # unless the order's net value reaches zero.
        shopify_net_by_order = {
            order_id: max(0.0, paid - shopify_refunded.get(order_id, 0.0))
            for order_id, paid in shopify_paid.items()
        }
        shopify_revenue = sum(shopify_net_by_order.values())
        shopify_orders = sum(1 for amount in shopify_net_by_order.values() if amount > 0)
        other_revenue = sum(float(r.get("amount") or 0) for r in other_approved) - sum(
            float(r.get("amount") or 0) for r in other_reversals
        )
        other_orders = max(0, len(other_approved) - len(other_reversals))

        revenue = other_revenue + shopify_revenue
        orders = other_orders + shopify_orders
        ticket = revenue / orders if orders else 0.0
        has_paid_events = bool(other_approved or shopify_paid)
        if not has_paid_events:
            message = "Nenhuma venda paga registrada ainda. O Hermes atualizará este painel ao receber o primeiro evento de pedido pago. "
        elif not orders and revenue <= 0:
            message = "Pedidos pagos registrados, mas totalmente revertidos por reembolsos ou estornos; receita líquida zero. "
        else:
            message = "Faturamento líquido de reembolsos em BRL, antes de taxas, comissões, impostos e custos de aquisição. Não é lucro. "
        if excluded_currencies:
            message += f"Moedas excluídas deste total: {', '.join(excluded_currencies)}."

        return {
            "range_start": range_start,
            "range_end": range_end,
            "revenue": round(revenue, 2),
            "orders": orders,
            "ticket": round(ticket, 2),
            "status": "ok",
            "message": message,
        }


# The API injects the persistent DB when the module is loaded by the application.
sales_service = None
