from app.services.controls import ControlService


def test_global_kill_switch_blocks_action():
    controls = ControlService()
    controls.set_kill_switch("global", True)
    result = controls.is_allowed("publish")
    assert result.allowed is False


def test_budget_blocks_expensive_action():
    controls = ControlService({"daily_budget": 10, "daily_spend": 9})
    result = controls.is_allowed("ai", estimated_cost=2)
    assert result.allowed is False


def test_low_cost_action_is_allowed():
    assert ControlService({"daily_budget": 10, "daily_spend": 1}).is_allowed("radar", 2).allowed
