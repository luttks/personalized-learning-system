# Frontend Guide

React 19 + TypeScript + Vite + Tailwind v4. Scripts: `npm run dev`, `npm run build`, `npm run lint`.

The Vite app uses `VITE_API_URL` (default `http://localhost:8000/api/v1`). Keep API calls in `src/api`, auth token refresh in `src/api/client.ts`, and page-level workflows in `src/pages`.
