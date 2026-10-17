from backend.app.domain.economics import estimate_profit


def test_estimate_profit_subtracts_all_recorded_costs():
    assert estimate_profit(1000, 100, 50, 75, 25) == 750.0
