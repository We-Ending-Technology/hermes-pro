from datetime import date

from .sales import SalesService


class AnalyticsService:
    def __init__(self, sales_service: SalesService):
        self.sales = sales_service

    async def insights(self, range_start: date | None = None, range_end: date | None = None) -> dict:
        summary = await self.sales.summary(range_start, range_end)
        if summary["status"] != "ok":
            return {"status": summary["status"], "insights": [summary["message"]], "experiments": ["Aguardando dados reais de vendas para comparar experimentos."]}
        orders = summary["orders"] or 0
        revenue = summary["revenue"] or 0.0
        ticket = summary["ticket"] or 0.0
        insights = [
            f"Receita persistida no período: R$ {revenue:.2f}.",
            f"Pedidos aprovados persistidos: {orders}.",
            f"Ticket médio calculado: R$ {ticket:.2f}."
        ]
        experiments = [
            "Registrar pelo menos uma alteração de oferta por vez para atribuir efeitos às vendas.",
            "Comparar períodos somente quando houver volume real suficiente."
        ]
        return {"status": "ok", "insights": insights, "experiments": experiments}


analytics_service = None
