# FastAPI routing, validation and error boundaries

## Existing public interfaces retained

- ASGI entry remains `backend.api.api:app`.
- Existing `/api/*` routes, including OAuth, RAG, analysis, workspace, usage and gallery, are unchanged.
- `backend/api/api.py` contains the original report/RAG endpoints and mounts the existing `product_api.router`.
- `backend/api/product_api.py` owns authenticated roadmap endpoints; `backend/services/` remains the business-logic layer.
- Report request schemas live in `backend/api/schemas.py`. Security checks and validation belong in `backend/security/` and Pydantic request models. Repository URLs must pass the existing SSRF-safe validator.

## Shared error handling

`backend/api/errors.py` centralizes:

- Safe Pydantic validation responses (no `input` values, no pasted secrets).
- Report/RAG known-error mapping to 400 and fixed internal-error responses to 500.
- Product feature error mapping, preserving provider-specific 429/502/503/504 behavior and original HTTP errors.

Do not return raw exception text for unexpected database/SDK/network faults. A local server should log sensitive details only through approved redacted logging; never log API keys or query strings.

## Add a new feature safely

1. Define a focused route in `backend/api/<feature>.py` with `APIRouter(prefix='/api')`.
2. Define bounded Pydantic input models and use existing URL/question validation.
3. Put reusable computations and third-party I/O in `backend/services/<feature>.py`.
4. Mount the router in the existing `backend/api/api.py` (or a future router registry only after integration tests are in place).
5. Apply authentication and workspace authorization consistently with existing endpoints.
6. Use the shared safe exception policy; test 200, 401, 403, 404, 422, 429 and 500 scenarios as applicable.
7. Add unit tests, API integration tests and browser checks; avoid altering Alembic revisions in place.

This refactor **does not** claim every older endpoint has been rewritten to the new boundary. It establishes a shared location and updates the existing report/product routing boundary without changing its outward behavior.
