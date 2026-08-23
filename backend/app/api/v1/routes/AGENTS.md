# Route Guide

- `exam.py`: student document analysis, diagnostic quiz, exam analysis and roadmap inputs.
- `content.py`: admin/course document upload jobs, analysis, preview, RAG index/search and catalog operations.
- `learners.py`, `student_profiles.py`: student profile and learning state.
- `catalog.py`, `course_learning_paths.py`, `personalized_roadmap.py`: course publishing and personalized paths.
- `diagnostics.py`: diagnostic assessment workflows.

When adding an endpoint, update the Pydantic schema, auth dependency, tests, and frontend API wrapper together.
