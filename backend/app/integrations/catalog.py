from dataclasses import dataclass
from enum import StrEnum

class Marketplace(StrEnum):
    MERCADO_LIVRE = "mercado_livre"
    SHOPEE = "shopee"
    AMAZON = "amazon"

@dataclass(frozen=True)
class MarketplaceConfig:
    enabled: bool = False
    api_base_url: str | None = None
    credential_env_var: str | None = None

DEFAULT_MARKETPLACE_CONFIG: dict[Marketplace, MarketplaceConfig] = {
    Marketplace.MERCADO_LIVRE: MarketplaceConfig(credential_env_var="MERCADO_LIVRE_ACCESS_TOKEN"),
    Marketplace.SHOPEE: MarketplaceConfig(credential_env_var="SHOPEE_ACCESS_TOKEN"),
    Marketplace.AMAZON: MarketplaceConfig(credential_env_var="AMAZON_ACCESS_TOKEN"),
}

class MarketplaceCatalog:
    def __init__(self, configs: dict[Marketplace, MarketplaceConfig] | None = None) -> None:
        self.configs = configs or DEFAULT_MARKETPLACE_CONFIG.copy()

    def enabled(self) -> list[Marketplace]:
        return [marketplace for marketplace, config in self.configs.items() if config.enabled]
