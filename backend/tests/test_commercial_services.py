from datetime import date

from backend.app.services.sales import SalesService
from backend.app.services.analytics import AnalyticsService


class FakeDB:
    def __init__(self, rows):
        self.rows = rows

    async def select(self, table, *, params=None):
        return self.rows


def test_sales_summary_aggregates_real_events():
    service = SalesService(FakeDB([
        {"amount": "49.90", "currency": "BRL", "event_type": "PURCHASE", "occurred_at": "2026-09-10T10:00:00+00:00"},
        {"amount": "79.90", "currency": "BRL", "event_type": "PURCHASE", "occurred_at": "2026-09-11T10:00:00+00:00"},
    ]))
    result = service.summary(date(2026, 9, 1), date(2026, 9, 30))
    assert result["status"] == "available"
    assert result["orders"] == 2
    assert result["revenue"] == 129.8
    assert result["ticket"] == 64.9


def test_analytics_reports_insufficient_data_without_fabricating_metrics():
    service = AnalyticsService(FakeDB([]))
    result = service.insights()
    assert result["status"] == "insufficient_data"
    assert result["insights"]
    assert result["experiments"]
