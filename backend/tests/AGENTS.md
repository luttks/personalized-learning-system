# Test Guide

Tests cover route contracts, services, document extraction/storage, RAG chunking, diagnostics, security and roadmap logic. `conftest.py` supplies test database/settings defaults. Prefer deterministic unit tests and fake providers; avoid network/API keys. Run `cd backend && pytest -q`.
