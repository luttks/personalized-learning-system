# Migration Guide

Alembic migrations are append-only and ordered by `down_revision`; inspect the current head before creating one. Migrations create the pgvector extension and evolve content, exam, learner, catalog, and roadmap tables.

Run from `backend`: `alembic upgrade head`. Never edit an already-applied migration to fix production data; add a corrective migration.
