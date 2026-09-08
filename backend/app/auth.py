from typing import Any

class AuthProvider:
    """Boundary for a future Supabase/JWT authentication implementation."""
    async def authenticate(self, token: str) -> dict[str, Any] | None:
        return None
