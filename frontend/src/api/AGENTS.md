# API Client Guide

Keep HTTP details and response types here. `client.ts` adds bearer tokens and refreshes on 401; do not bypass it for authenticated requests. Use `FormData` for document uploads and keep `VITE_API_URL` configurable.
