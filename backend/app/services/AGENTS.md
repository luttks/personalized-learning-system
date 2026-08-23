# Service Guide

Services own domain workflows. Key modules:
- `exam_service.py`: text/OCR document analysis, LLM quiz generation, exam analysis and roadmap generation. Its `.docx` reader uses Open XML directly.
- `document_extractor.py`: PDF/DOCX/PPTX/TXT extraction and OCR.
- `document_storage.py`: validated, checksummed file storage under `uploads/documents`.
- `document_analysis_service.py`: Celery analysis job and `DocumentAnalysis` persistence.
- `content_service.py`: course/version/document/job lifecycle.
- `rag_service.py`: split chunks, embed, replace index, hybrid vector + lexical search.
- `catalog_service.py`, `course_learning_path_service.py`: course structure and learning paths.
- `diagnostic*`, `mastery_service.py`, `learner*`, `roadmap_planner.py`: learner state and personalization.

RAG is not automatic for the student exam upload path. Course RAG requires a completed analysis and an explicit rebuild/index call.
