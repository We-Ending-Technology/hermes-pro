class AnalyticsService:
    def insights(self, range_start=None, range_end=None) -> dict:
        return {
            "status": "insufficient_data",
            "insights": [
                "Ainda não há pedidos pagos suficientes para calcular conversão, ticket médio ou lucro. O painel só deve exibir métricas após receber eventos reais do checkout."
            ],
            "experiments": [
                "Valide uma página de produto por vez, registre visitas e pedidos pagos e só então compare preço, oferta e origem do tráfego."
            ],
        }


analytics_service = AnalyticsService()
