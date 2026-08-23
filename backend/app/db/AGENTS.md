# Database Access Guide

`base.py` holds declarative metadata/mixins; `session.py` creates the async SQLAlchemy engine/session. Route dependencies provide request-scoped sessions. Keep transactions explicit and commit only after a complete domain update.
