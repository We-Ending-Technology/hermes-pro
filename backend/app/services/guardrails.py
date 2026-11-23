"""Runtime safety gates for side-effectful Hermes actions.

AI-generated plans and opportunity payloads are untrusted input. These checks are
deterministic and run server-side immediately before an external side effect.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailDecision:
    allowed: bool
    reason: str


def authorize_external_action(
    *,
    kill_switch: bool,
    external_actions_enabled: bool,
    action_enabled: bool,
    configured_limit: float,
    requested_amount: float,
) -> GuardrailDecision:
    """Fail closed unless every gate passes; never infer permission from AI output."""
    if kill_switch:
        return GuardrailDecision(False, "Hermes kill switch is active")
    if not external_actions_enabled:
        return GuardrailDecision(False, "external actions are disabled")
    if not action_enabled:
        return GuardrailDecision(False, "this action is not explicitly enabled")
    if configured_limit <= 0:
        return GuardrailDecision(False, "no positive owner-approved limit is configured")
    if requested_amount <= 0:
        return GuardrailDecision(False, "requested amount must be positive")
    if requested_amount > configured_limit:
        return GuardrailDecision(False, "requested amount exceeds the configured limit")
    return GuardrailDecision(True, "allowed by configured runtime policy")
