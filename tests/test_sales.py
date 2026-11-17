import pytest

from backend.app.services.sales import SalesService


class FakeSupabase:
    def __init__(self, rows):
        self.rows = rows
        self.params = None

    async def select(self, table, params=None):
        assert table == "hermes_sales_events"
        self.params = params or {}
        return self.rows


@pytest.mark.asyncio
async def test_sales_total_counts_brl_only_and_subtracts_reversals():
    service = SalesService(FakeSupabase([
        {"provider": "kiwify", "event_type": "PURCHASE_APPROVED", "amount": 100.0, "currency": "BRL"},
        {"provider": "kiwify", "event_type": "PURCHASE_APPROVED", "amount": 50.0, "currency": "BRL"},
        {"provider": "kiwify", "event_type": "PURCHASE_REFUNDED", "amount": 20.0, "currency": "BRL"},
        {"provider": "kiwify", "event_type": "PURCHASE_APPROVED", "amount": 900.0, "currency": "USD"},
        {"provider": "shopify", "event_type": "PURCHASE_APPROVED", "amount": 90.0, "currency": "BRL"},
    ]))
    result = await service.summary()
    assert result["revenue"] == 220.0
    assert result["orders"] == 2
    assert "provider.eq.shopify" in service.db.params["or"]
    assert "USD" in result["message"]
    assert "Não é lucro" in result["message"]


@pytest.mark.asyncio
async def test_unknown_currency_is_not_assumed_to_be_brl():
    service = SalesService(FakeSupabase([
        {"provider": "hotmart", "event_type": "PURCHASE_APPROVED", "amount": 150.0, "currency": None},
    ]))
    result = await service.summary()
    assert result["revenue"] == 0
    assert result["orders"] == 0
    assert "SEM_MOEDA" in result["message"]
