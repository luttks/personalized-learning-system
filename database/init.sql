CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

SELECT extname
FROM pg_extension
WHERE extname IN ('vector', 'pgcrypto');