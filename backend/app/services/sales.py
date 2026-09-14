from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal


PURCHASE_EVENTS = {"PURCHASE", "PURCHASE_APPROVED", "PURCHASE_COMPLETE", "PURCHASE_COMPLETED", "SALE"}


class SalesService:
    def __init__(self, db):
        self.db = db

    async def summary(self, range_start: date | None = None, range_end: date | None = None) -> dict:
        params = {"select": "amount,currency,event_type,occurred_at", "order": "occurred_at.asc"}
        filters = []
        if range_start:
            filters.append(f"occurred_at.gte.{datetime.combine(range_start, time.min, tzinfo=timezone.utc).isoformat()}")
        if range_end:
            filters.append(f"occurred_at.lte.{datetime.combine(range_end, time.max, tzinfo=timezone.utc).isoformat()}")
        if len(filters) == 1:
            params["occurred_at"] = filters[0].split("occurred_at.", 1)[1]
        elif filters:
            params["and"] = f"({','.join(filters)})"

        rows = await self.db.select("hermes_sales_events", params=params)
        purchases = [
            row for row in rows
            if str(row.get("event_type", "")).upper() in PURCHASE_EVENTS and row.get("amount") is not None
        ]
        amounts = [Decimal(str(row["amount"])) for row in purchases]
        revenue = sum(amounts, Decimal("0"))
        orders = len(amounts)
        ticket = revenue / orders if orders else None
        currency = next((row.get("currency") for row in purchases if row.get("currency")), "BRL")

        if not purchases:
            return {
                "range_start": range_start,
                "range_end": range_end,
                "revenue": None,
                "orders": None,
                "ticket": None,
                "status": "insufficient_data",
                "message": "Nenhuma venda aprovada registrada no Supabase para o período.",
            }

        return {
            "range_start": range_start,
            "range_end": range_end,
            "revenue": float(revenue),
            "orders": orders,
            "ticket": float(ticket) if ticket is not None else None,
            "status": "available",
            "message": f"Dados reais registrados em {currency}.",
        }


sales_service = None
