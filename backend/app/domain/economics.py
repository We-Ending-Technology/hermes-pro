from __future__ import annotations


def estimate_profit(
    revenue: float,
    ai_cost: float,
    infra_cost: float,
    ads_cost: float,
    other_cost: float,
) -> float:
    return round(float(revenue) - float(ai_cost) - float(infra_cost) - float(ads_cost) - float(other_cost), 2)
