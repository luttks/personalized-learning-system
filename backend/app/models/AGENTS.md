# Model Guide

SQLAlchemy models define PostgreSQL persistence. Content lifecycle is `Course -> CourseVersion -> Document -> DocumentJob/DocumentAnalysis`; RAG rows are `ContentChunk`.

`ContentChunk.embedding` is a nullable 768-dimensional pgvector column. Nullable supports migrations/rebuilds; new chunks should always receive a vector and `embedding_model`.
