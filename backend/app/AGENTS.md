# Application Guide

`main.py` creates FastAPI, configures CORS, cleans stale temp uploads, and mounts `/api/v1`.
The API router registers auth, profiles, learners, courses/catalog, diagnostics, content/RAG, exams, and roadmaps.

Trace a feature as: route -> service -> model/schema -> migration. Keep authentication through shared dependencies in `api/dependencies/auth.py`.
