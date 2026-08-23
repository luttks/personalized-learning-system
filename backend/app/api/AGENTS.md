# API Guide

Public HTTP boundary. Keep authorization and status-code mapping here; do not duplicate domain logic from services. API prefix is `/api/v1`.

`dependencies/` supplies current-user/role/session dependencies. `v1/routes/` contains feature endpoints. Keep request/response schemas in `backend/app/schemas`.
