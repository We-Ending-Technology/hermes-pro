from .core.config import Settings

class Database:
    """Database boundary; migrations live under supabase/migrations."""
    def __init__(self, settings: Settings) -> None:
        self.url = settings.database_url
