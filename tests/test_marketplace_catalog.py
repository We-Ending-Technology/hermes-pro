from backend.app.integrations.catalog import Marketplace, MarketplaceCatalog

def test_marketplaces_are_disabled_by_default() -> None:
    catalog = MarketplaceCatalog()
    assert catalog.enabled() == []
    assert catalog.configs[Marketplace.MERCADO_LIVRE].credential_env_var == "MERCADO_LIVRE_ACCESS_TOKEN"
    assert catalog.configs[Marketplace.SHOPEE].credential_env_var == "SHOPEE_ACCESS_TOKEN"
    assert catalog.configs[Marketplace.AMAZON].credential_env_var == "AMAZON_ACCESS_TOKEN"
