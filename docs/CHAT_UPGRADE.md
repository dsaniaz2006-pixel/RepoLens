# Conversational chat — current status

Persistent private conversations, follow-up context, revision-pinned citations,
hybrid retrieval, reload/delete controls, leases and ownership checks are implemented.
SQLite remains the default. PostgreSQL conversation storage, PostgreSQL authentication
and an explicit offline account/chat/workspace migration tool are now included.

Upgrades 2–10 are no longer future-only placeholders. Their implementation and
verification boundaries are documented in RELEASE_READINESS.md. That file is the
current source of truth for the entire project; this document's older future-work
list has been removed.

Use START_HERE.md to update your existing installation without creating another
virtual environment. Existing saved answers do not change when code is updated;
start a new conversation to exercise the current retrieval/model path.
