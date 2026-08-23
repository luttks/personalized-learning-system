# Auth UI Guide

`AuthContext` owns login/logout/token state; `RouteGuards` enforces guest/authenticated/role access. Keep token storage keys and refresh behavior centralized in `src/api/client.ts`.
