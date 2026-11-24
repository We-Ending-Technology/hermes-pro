import unittest

from backend.app.services.ai_budget import get_ai_budget_status


class FakeDatabase:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error

    async def select(self, table, params=None):
        if self.error:
            raise self.error
        if table != "hermes_settings":
            raise AssertionError(f"unexpected table: {table}")
        return self.rows


class AIBudgetGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_zero_ai_budget_blocks_external_calls(self):
        db = FakeDatabase([{
            "kill_switch": False,
            "daily_ai_budget": "0",
            "daily_total_budget": "0",
        }])
        status = await get_ai_budget_status(db)
        self.assertFalse(status["allowed"])
        self.assertEqual(status["reason"], "zero_budget")

    async def test_kill_switch_blocks_even_with_positive_budget(self):
        db = FakeDatabase([{
            "kill_switch": True,
            "daily_ai_budget": "10",
            "daily_total_budget": "20",
        }])
        status = await get_ai_budget_status(db)
        self.assertFalse(status["allowed"])
        self.assertEqual(status["reason"], "kill_switch")

    async def test_missing_budget_record_fails_closed(self):
        status = await get_ai_budget_status(FakeDatabase())
        self.assertFalse(status["allowed"])
        self.assertEqual(status["reason"], "budget_state_missing")

    async def test_database_error_fails_closed(self):
        status = await get_ai_budget_status(FakeDatabase(error=RuntimeError("db offline")))
        self.assertFalse(status["allowed"])
        self.assertEqual(status["reason"], "budget_state_unavailable")

    async def test_positive_budgets_enable_ai_gate(self):
        db = FakeDatabase([{
            "kill_switch": False,
            "daily_ai_budget": "5.00",
            "daily_total_budget": "10.00",
        }])
        status = await get_ai_budget_status(db)
        self.assertTrue(status["allowed"])
        self.assertEqual(status["reason"], "budget_configured")


if __name__ == "__main__":
    unittest.main()
