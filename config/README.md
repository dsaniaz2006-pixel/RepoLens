# Environment configuration, not application code

The only committed template is `../.env.example`. Copy that file to `../.env` or copy your existing working private `.env`. Keep the real file on your own computer and out of ZIP uploads. There is no secret or certificate in this folder.

`backend/core/environment.py` loads the private root `.env` without overriding environment variables. `start.mjs` and `frontend/vite.config.js` keep their existing validated HTTPS and API proxy settings.

See [environment reference](../docs/ENVIRONMENT.md) and [local HTTPS setup](../docs/guides/LOCAL_HTTPS_SETUP.md). Do not move the actual `.env` into `config/` without changing the documented loader and verifying OAuth plus database connection.
