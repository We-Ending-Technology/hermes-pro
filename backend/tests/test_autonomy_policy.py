from app.services.controls import ControlService


def test_human_approval_action_is_blocked_without_approval():
    controls = ControlService()
    result = controls.is_allowed("publish")
    assert result.allowed is False
    assert "approval" in result.reason


def test_reversible_action_remains_allowed_when_budget_is_available():
    controls = ControlService({"daily_budget": 10, "daily_spend": 1})
    assert controls.is_allowed("retry_job", estimated_cost=2).allowed


def test_unknown_action_is_not_implicitly_dangerous():
    controls = ControlService()
    result = controls.is_allowed("unknown_action")
    assert result.allowed is False
