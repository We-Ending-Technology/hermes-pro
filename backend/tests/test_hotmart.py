from backend.app.core.config import Settings
from backend.app.integrations.hotmart import HotmartAdapter


def test_hotmart_capabilities_do_not_claim_unsupported_product_creation():
    adapter = HotmartAdapter(Settings())
    capabilities = adapter.publication_capabilities()
    assert capabilities["product_create"]["supported"] is False
    assert capabilities["product_list"]["supported"] is True
    assert capabilities["sales_history"]["supported"] is True
    assert capabilities["webhooks"]["supported"] is True
