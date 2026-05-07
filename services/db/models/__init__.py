"""Re-export models so Alembic autogenerate sees their metadata."""

from services.db.models.user import User

__all__ = ["User"]
