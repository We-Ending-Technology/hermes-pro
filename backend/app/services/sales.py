from datetime import date, datetime, time, timezone
from typing import Any

from ..db.supabase import SupabaseREST


class SalesService:
    def __init__(self, db: SupabaseREST):
        self.db = db

    async def summary(self, range_start: date | None = None, range_end: date | None = None) -> dict[str, Any]:
        params = {"select": "amount,currency,event_type,occurred_at", "provider": "eq.hotmart", "order": "occurred_at.desc"}
        if range_start:
            params["occurred_at"] = f"gte.{datetime.combine(range_start, time.min, tzinfo=timezone.utc).isoformat()}"
        if range_end:
            params["occurred_at"] = f"lte.{datetime.combine(range_end, time.max, tzinfo=timezone.utc).isoformat()}"
        try:
            rows = await self.db.select("hermes_sales_events", params=params)
        except Exception as exc:
            return {"range_start": range_start, "range_end": range_end, "revenue": None, "orders": None, "ticket": None, "status": "error", "message": f"Falha ao consultar vendas reais: {exc}"}
        approved = [r for r in rows if str(r.get("event_type", "")).upper() in {"PURCHASE_APPROVED", "PURCHASE_COMPLETE", "PURCHASE_APPROVED_EVENT"}]
        amounts = [float(r["amount"]) for r in approved if r.get("amount") is not None]
        revenue = sum(amounts) if amounts else 0.0
        orders = len(approved)
        ticket = revenue / orders if orders else 0.0
        return {"range_start": range_start, "range_end": range_end, "revenue": revenue, "orders": orders, "ticket": ticket, "status": "ok", "message": "Dados calculados a partir dos eventos Hotmart persistidos."}


# The API injects the persistent DB when the module is loaded by the application.
sales_service = None
