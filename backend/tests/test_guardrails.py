from app.services.guardrails import authorize_external_action


def test_kill_switch_blocks_even_when_other_gates_pass():
    result = authorize_external_action(
        kill_switch=True,
        external_actions_enabled=True,
        action_enabled=True,
        configured_limit=100,
        requested_amount=25,
    )
    assert result.allowed is False
    assert "kill switch" in result.reason


def test_external_actions_disabled_by_default_policy_blocks():
    result = authorize_external_action(
        kill_switch=False,
        external_actions_enabled=False,
        action_enabled=True,
        configured_limit=100,
        requested_amount=25,
    )
    assert result.allowed is False


def test_zero_limit_fails_closed():
    result = authorize_external_action(
        kill_switch=False,
        external_actions_enabled=True,
        action_enabled=True,
        configured_limit=0,
        requested_amount=1,
    )
    assert result.allowed is False


def test_amount_above_limit_is_blocked():
    result = authorize_external_action(
        kill_switch=False,
        external_actions_enabled=True,
        action_enabled=True,
        configured_limit=50,
        requested_amount=50.01,
    )
    assert result.allowed is False


def test_all_explicit_gates_and_limit_allow_action():
    result = authorize_external_action(
        kill_switch=False,
        external_actions_enabled=True,
        action_enabled=True,
        configured_limit=50,
        requested_amount=50,
    )
    assert result.allowed is True
