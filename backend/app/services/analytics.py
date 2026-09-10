class AnalyticsService:
    def insights(self, range_start=None, range_end=None) -> dict:
        return {"status": "insufficient_data", "insights": ["Conecte o fluxo de vendas do Hotmart para liberar métricas reais."], "experiments": ["Teste um único posicionamento por produto e registre vendas reais antes de comparar conversão."]}

analytics_service = AnalyticsService()
