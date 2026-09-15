from app.services.lifecycle import calculate_operating_profit, retry_policy, transition_job


def test_valid_job_transition_is_allowed():
    assert transition_job("pending", "running").allowed


def test_invalid_job_transition_is_blocked():
    assert not transition_job("pending", "published").allowed


def test_retry_policy_stops_at_limit():
    assert retry_policy(3, 3) == (False, 0)


def test_operating_profit_uses_recorded_costs():
    assert calculate_operating_profit(100, [10, 5.5]) == 84.5
