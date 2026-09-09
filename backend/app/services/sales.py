from datetime import date

class SalesService:
    def summary(self, range_start: date | None = None, range_end: date | None = None) -> dict:
        return {"range_start": range_start, "range_end": range_end, "revenue": None, "orders": None, "ticket": None, "status": "unavailable", "message": "Nenhuma venda real foi carregada do Hotmart ainda."}

sales_service = SalesService()
