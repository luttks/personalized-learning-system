# Page Guide

Pages are routed in `App.tsx` and protected by `RouteGuards`. Student routes include profile, personalized onboarding/post-exam and roadmap; admin routes include users and course management. Avoid duplicating API logic in pages; call typed wrappers from `src/api`.
