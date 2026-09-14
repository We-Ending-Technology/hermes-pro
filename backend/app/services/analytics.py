from __future__ import annotations

from datetime import date


class AnalyticsService:
    def __init__(self, db):
        self.db = db

    async def insights(self, range_start: date | None = None, range_end: date | None = None) -> dict:
        params = {"select": "amount,event_type,occurred_at,payload", "order": "occurred_at.asc"}
        rows = await self.db.select("hermes_sales_events", params=params)
        purchases = [
            row for row in rows
            if str(row.get("event_type", "")).upper() in {"PURCHASE", "PURCHASE_APPROVED", "PURCHASE_COMPLETE", "PURCHASE_COMPLETED", "SALE"}
            and row.get("amount") is not None
        ]
        if not purchases:
            return {
                "status": "insufficient_data",
                "insights": ["Ainda não há vendas reais suficientes para gerar uma análise de desempenho."],
                "experiments": ["Depois das primeiras vendas, compare produtos e posicionamentos com base em dados reais."],
            }

        revenue = sum(float(row["amount"]) for row in purchases)
        orders = len(purchases)
        ticket = revenue / orders
        insights = [f"Foram registradas {orders} vendas, com receita total de {revenue:.2f} e ticket médio de {ticket:.2f}."]
        experiments = [
            "Identifique o produto com maior receita antes de aumentar a produção.",
            "Teste uma variação de posicionamento por vez e compare o resultado com o período anterior.",
        ]
        return {"status": "available", "insights": insights, "experiments": experiments}


analytics_service = None
