# Database Guide

`init.sql` runs only when the PostgreSQL volume is first created. It enables `vector` and `pgcrypto`; schema changes belong in Alembic, not this file. To recreate a local database, `docker-compose down -v` is destructive and removes stored data.
