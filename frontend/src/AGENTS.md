# Frontend Source Guide

- `api/`: typed Axios wrappers matching FastAPI endpoints; use `getApiErrorMessage` for user-facing errors.
- `auth/`: auth context, token/session guards.
- `components/`: shared shell and UI primitives.
- `pages/`: route screens; `PersonalizedLearningPage` owns student upload/analyze/quiz/roadmap flow, while `CourseManagementPage` owns admin/course content management.
- `types/`: shared TypeScript API/domain types.

When changing a backend response, update the matching API type and page state handling together. Preserve auth role guards and the `/api/v1` base URL convention.
