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
            "select": "amount,currency,event_type,occurred_at,provider",
            "or": "(provider.eq.hotmart,provider.eq.kiwify)",
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

        approved = [r for r in rows if str(r.get("event_type", "")).upper() in APPROVED_EVENTS]
        reversals = [r for r in rows if str(r.get("event_type", "")).upper() in REVERSAL_EVENTS]
        revenue = sum(float(r.get("amount") or 0) for r in approved) - sum(
            float(r.get("amount") or 0) for r in reversals
        )
        orders = max(0, len(approved) - len(reversals))
        ticket = revenue / orders if orders else 0.0
        return {
            "range_start": range_start,
            "range_end": range_end,
            "revenue": round(revenue, 2),
            "orders": orders,
            "ticket": round(ticket, 2),
            "status": "ok",
            "message": "Vendas aprovadas e estornos recebidos por webhook Hotmart/Kiwify.",
        }


# The API injects the persistent DB when the module is loaded by the application.
sales_service = None
