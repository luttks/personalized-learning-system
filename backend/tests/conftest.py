import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test"
)
os.environ.setdefault(
    "ALEMBIC_DATABASE_URL", "postgresql+psycopg://test:test@localhost/test"
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-characters")
