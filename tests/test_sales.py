from backend.app.services.sales import SalesService

class FakeSupabase:
    def __init__(self, rows):
        self.rows = rows
        self.params = None

    async def select(self, table, params=None):
        assert table == "hermes_sales_events"
        self.params = params or {}
        return self.rows


async def test_sales_total_counts_brl_only_and_subtracts_reversals():
    service = SalesService(FakeSupabase([
        {"provider": "kiwify", "event_type": "PURCHASE_APPROVED", "amount": 100.0, "currency": "BRL"},
        {"provider": "kiwify", "event_type": "PURCHASE_APPROVED", "amount": 50.0, "currency": "BRL"},
        {"provider": "kiwify", "event_type": "PURCHASE_REFUNDED", "amount": 20.0, "currency": "BRL"},
        {"provider": "kiwify", "event_type": "PURCHASE_APPROVED", "amount": 900.0, "currency": "USD"},
        {"provider": "shopify", "event_type": "PURCHASE_APPROVED", "amount": 90.0, "currency": "BRL", "external_id": "orders/paid:123"},
        {"provider": "shopify", "event_type": "PURCHASE_REFUNDED", "amount": 20.0, "currency": "BRL", "external_id": "refunds/create:123:900"},
        {"provider": "shopify", "event_type": "PURCHASE_REFUNDED", "amount": 10.0, "currency": "BRL", "external_id": "refunds/create:123:901"},
    ]))
    result = await service.summary()
    assert result["revenue"] == 190.0
    assert result["orders"] == 2
    assert "provider.eq.shopify" in service.db.params["or"]
    assert "USD" in result["message"]
    assert "Não é lucro" in result["message"]


async def test_shopify_fully_refunded_order_is_removed_from_net_order_count():
    service = SalesService(FakeSupabase([
        {"provider": "shopify", "event_type": "PURCHASE_APPROVED", "amount": 50.0, "currency": "BRL", "external_id": "orders/paid:456"},
        {"provider": "shopify", "event_type": "PURCHASE_REFUNDED", "amount": 20.0, "currency": "BRL", "external_id": "refunds/create:456:901"},
        {"provider": "shopify", "event_type": "PURCHASE_REFUNDED", "amount": 30.0, "currency": "BRL", "external_id": "refunds/create:456:902"},
    ]))
    result = await service.summary()
    assert result["revenue"] == 0.0
    assert result["orders"] == 0
    assert "totalmente revertidos" in result["message"]


async def test_no_sales_message_does_not_claim_revenue():
    service = SalesService(FakeSupabase([]))
    result = await service.summary()
    assert result["revenue"] == 0.0
    assert result["orders"] == 0
    assert "Nenhuma venda paga" in result["message"]
