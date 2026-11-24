from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _amount(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


async def get_ai_budget_status(db: Any) -> dict[str, Any]:
    """Fail closed unless the persisted operator budget explicitly allows AI use.

    A zero or missing budget is a hard no-spend switch. This is an enablement
    guard, not a spend meter; positive budgets still require separate usage
    accounting before they can be treated as a guaranteed monetary cap.
    """
    try:
        rows = await db.select(
            "hermes_settings",
            params={
                "select": "kill_switch,daily_ai_budget,daily_total_budget",
                "id": "eq.true",
                "limit": "1",
            },
        )
    except Exception:
        return {
            "allowed": False,
            "reason": "budget_state_unavailable",
            "message": "Não foi possível confirmar o orçamento de IA; chamadas externas bloqueadas.",
            "daily_ai_budget": None,
            "daily_total_budget": None,
        }

    if not rows:
        return {
            "allowed": False,
            "reason": "budget_state_missing",
            "message": "Configuração de orçamento ausente; chamadas externas bloqueadas.",
            "daily_ai_budget": None,
            "daily_total_budget": None,
        }

    row = rows[0]
    ai_budget = _amount(row.get("daily_ai_budget"))
    total_budget = _amount(row.get("daily_total_budget"))

    if row.get("kill_switch") is True:
        reason = "kill_switch"
        message = "Kill switch ativo; chamadas externas de IA bloqueadas."
        allowed = False
    elif ai_budget <= 0 or total_budget <= 0:
        reason = "zero_budget"
        message = "Orçamento diário de IA ou orçamento total está zerado; chamadas externas bloqueadas."
        allowed = False
    else:
        reason = "budget_configured"
        message = "Orçamento de IA configurado."
        allowed = True

    return {
        "allowed": allowed,
        "reason": reason,
        "message": message,
        "daily_ai_budget": str(ai_budget),
        "daily_total_budget": str(total_budget),
    }
