# Core Guide

- `config.py`: Pydantic settings loaded from `.env`; LLM keys are exposed as filtered lists.
- `llm_client.py`: Gemini-first key rotation with Groq/OpenAI-compatible fallback; JSON requests use `response_format` where supported.
- `security.py`, `jwt.py`: password hashing and token primitives.

Do not log credentials. If an LLM model changes, verify it against the provider's `/models` endpoint and rebuild/restart containers because settings are loaded at process startup.
