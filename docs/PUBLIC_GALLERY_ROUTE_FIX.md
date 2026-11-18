# Public Gallery route regression — RepoLens 27

## Symptom

`python -m pytest -q tests/test_product_upgrade.py` failed in
`test_public_gallery_is_accessible_without_account` with HTTP **404** at
`GET /gallery/`. The error occurred even with functioning React/Vite UI tests.

## Root cause

FastAPI used to mount `frontend/dist` only if it existed when
`backend.api.api` was first imported. Running an isolated Python test before
`npm run build` means that directory may not exist, so there was **no route**
for `/gallery/`. Building assets after the module was already imported did not
retroactively register the missing route.

## Correction

`backend/api/public_gallery.py` registers **explicit, read-only, anonymous**
Gallery routes before the optional frontend mount:

- `/gallery/` — approved public landing HTML
- `/gallery/gallery.css` — approved Gallery stylesheet
- `/gallery/<slug>/` and `/gallery/<slug>/index.html` — approved public source
  snapshots (strict ASCII slug validation; no arbitrary paths)

The older gallery test also expected the obsolete wording "Cached example report"; the actual public page correctly labels the entry "Source snapshot — AI review pending". The test now checks the truthful status instead of restoring a misleading claim.

When compiled assets exist in `frontend/dist`, they take priority. Otherwise
these specific pages use bundled public HTML sources. This does not grant
access to private reports, project configuration, or source files.

For a complete styled production website, `npm run build` remains required;
other global frontend assets are still served by the normal compiled site or
Vite dev server. HTTPS/OAuth, database, RAG and sessions were not changed.

## Test-first verification

`tests/test_public_gallery_route_tdd.py` initially failed because the router
was missing. After registration it passes, covering the unbuilt source,
compiled preference, source snapshots, the stylesheet, and private-path
rejections.

### Mac commands

From the RepoLens project root, with the Python environment activated:

```bash
python -m pytest -q tests/test_public_gallery_route_tdd.py
python -m pytest -q tests/test_product_upgrade.py -k test_public_gallery_is_accessible_without_account
```

Run the full pre-deployment gate only after frontend dependencies are present
and ports 5173, 5175 and 8000 are free:

```bash
bash scripts/verify_predeploy.sh
```

Do not approve deployment if any required gate still fails or is skipped.
