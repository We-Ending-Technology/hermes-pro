from datetime import date, datetime, time, timezone
from typing import Any

from ..db.supabase import SupabaseREST


class SalesService:
    def __init__(self, db: SupabaseREST):
        self.db = db

    async def summary(self, range_start: date | None = None, range_end: date | None = None) -> dict[str, Any]:
        params = {"select": "amount,currency,event_type,occurred_at", "provider": "eq.hotmart", "order": "occurred_at.desc"}
        try:
            rows = await self.db.select("hermes_sales_events", params=params)
        except Exception as exc:
            return {"range_start": range_start, "range_end": range_end, "revenue": None, "orders": None, "ticket": None, "status": "error", "message": f"Falha ao consultar vendas reais: {exc}"}
        start_dt = datetime.combine(range_start, time.min, tzinfo=timezone.utc) if range_start else None
        end_dt = datetime.combine(range_end, time.max, tzinfo=timezone.utc) if range_end else None
        filtered = []
        for row in rows:
            try:
                occurred = datetime.fromisoformat(str(row.get("occurred_at", "")).replace("Z", "+00:00"))
            except ValueError:
                continue
            if start_dt and occurred < start_dt:
                continue
            if end_dt and occurred > end_dt:
                continue
            filtered.append(row)
        approved = [r for r in filtered if str(r.get("event_type", "")).upper() in {"PURCHASE_APPROVED", "PURCHASE_COMPLETE", "PURCHASE_APPROVED_EVENT"}]
        amounts = [float(r["amount"]) for r in approved if r.get("amount") is not None]
        revenue = sum(amounts) if amounts else 0.0
        orders = len(approved)
        ticket = revenue / orders if orders else 0.0
        return {"range_start": range_start, "range_end": range_end, "revenue": revenue, "orders": orders, "ticket": ticket, "status": "ok", "message": "Dados calculados a partir dos eventos Hotmart persistidos."}


sales_service = None
