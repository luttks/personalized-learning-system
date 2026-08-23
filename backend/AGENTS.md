# Backend Guide

FastAPI application, async SQLAlchemy/PostgreSQL persistence, Redis/Celery background work, and Alembic migrations.

## Commands
- Local API: `python3.13 -m venv .venv && source .venv/bin/activate`; install `requirements.txt`; `alembic upgrade head`; `uvicorn app.main:app --reload`.
- Worker: `celery -A app.worker.celery_app:celery_app worker --loglevel=INFO`.
- Tests: `pytest -q`; targeted tests can run from `backend`.

## Boundaries
- Route handlers validate/authenticate/request-map and delegate business logic.
- Services contain workflows and persistence orchestration.
- Models are SQLAlchemy tables; schemas are Pydantic API contracts.
- Do not call external LLMs in unit tests; use fixtures/mocks and deterministic fallbacks.
