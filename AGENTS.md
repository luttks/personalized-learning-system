# Repository Guide

## Project map
- `backend/`: FastAPI API, SQLAlchemy models, Alembic migrations, Celery worker and tests.
- `frontend/`: React 19 + TypeScript + Vite UI.
- `database/`: PostgreSQL bootstrap SQL; Compose uses pgvector/pg17.
- `docs/`: design and implementation notes.
- `uploads/`: runtime document storage; do not commit or inspect recursively unless debugging a specific file.

## Run
This machine uses legacy `docker-compose` (not `docker compose`): `cp .env.example .env`, set database/JWT/LLM values, then `docker-compose up --build`. Services are frontend `5173`, backend `8000`, PostgreSQL `5432`, Redis `6379`.

## Conventions
- Preserve existing Vietnamese user-facing messages and API response shapes.
- Keep secrets in `.env`; never print or commit API keys.
- Apply database changes through a new Alembic migration, never by editing old migrations.
- The repo may contain local worktree changes; inspect before editing and do not reset them.
- Test backend with `cd backend && pytest -q`; lint/build frontend with `cd frontend && npm run lint && npm run build`.

## Important flows
- Student exam upload (`/learners/me/exams/analyze-document`) extracts text/OCR and sends `raw_text` to the LLM; it does not automatically build a vector index.
- Course document upload (`/courses/{course_id}/documents`) stores a version and queues verification/analysis through Celery. RAG chunks/embeddings are built separately by `/courses/versions/{version_id}/rag/index`.
- RAG data is in PostgreSQL `content_chunks` using pgvector. Gemini embeddings are preferred; local feature hashing is a fallback.
