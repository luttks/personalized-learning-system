# Worker Guide

Celery tasks execute long document verification/analysis outside request handlers. `verify_document_upload_task` verifies storage, extracts text/OCR, calls optional LLM analysis, and persists status/error details. Keep tasks synchronous at the Celery boundary and use `asyncio.run` for async services; dispose the async engine after task completion.
