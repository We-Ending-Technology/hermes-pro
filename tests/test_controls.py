from backend.app.domain.controls import control_allows


def test_global_kill_switch_blocks_every_action():
    allowed, reason = control_allows("produce", {"kill_switch": True})
    assert allowed is False
    assert reason == "global_kill_switch"


def test_domain_pause_blocks_matching_action():
    allowed, reason = control_allows(
        "publish", {"kill_switch": False, "paused_domains": ["publishing"]}
    )
    assert allowed is False
    assert reason == "domain_paused"


def test_budget_limit_blocks_when_daily_spend_reaches_limit():
    allowed, reason = control_allows(
        "produce",
        {"kill_switch": False, "daily_ai_spend": 10, "daily_ai_budget": 10},
    )
    assert allowed is False
    assert reason == "budget_exceeded"


def test_allowed_action_passes_controls():
    allowed, reason = control_allows("radar", {"kill_switch": False})
    assert allowed is True
    assert reason == "allowed"
