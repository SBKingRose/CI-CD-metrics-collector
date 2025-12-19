import sys
from pathlib import Path

# Add parent directory to path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Base, engine
from app.config import settings
from sqlalchemy import text


def _sqlite_add_column_if_missing(table: str, column: str, ddl_type: str, default_sql: str | None = None):
    """Non-destructive migration helper for SQLite (preserves existing data)."""
    if "sqlite" not in settings.database_url.lower():
        return
    with engine.connect() as conn:
        cols = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        existing = {c[1] for c in cols}  # name is index 1
        if column in existing:
            return
        ddl = f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"
        if default_sql is not None:
            ddl += f" DEFAULT {default_sql}"
        conn.execute(text(ddl))
        conn.commit()


def run_non_destructive_migrations():
    # Build steps: store bitbucket step UUID, best-effort log excerpt, and size factor
    _sqlite_add_column_if_missing("build_steps", "step_uuid", "TEXT")
    _sqlite_add_column_if_missing("build_steps", "log_excerpt", "TEXT")
    _sqlite_add_column_if_missing("build_steps", "size_factor", "INTEGER", "1")

if __name__ == "__main__":
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    run_non_destructive_migrations()
    print(f"Database initialized at {settings.database_url}")

