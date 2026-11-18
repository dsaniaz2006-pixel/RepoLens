> Historical document from an earlier build. See COMPLETION_REPORT.md for current implementation and verification status.

# Authentication integration verification

Date: 2026-10-18

## Implemented

1. Signup through Google OIDC or GitHub OAuth. First valid provider identity creates a persistent account.
2. Returning-user login through either provider, with stable provider/subject identity, opaque server sessions, and logout.
3. Landing → signup/login → authenticated workspace navigation. React waits for a server-confirmed session before rendering. FastAPI protects dashboard HTML, report/history/download routes, analysis/index/Q&A routes, and API documentation. New reports are scoped to the signed-in account.
4. Replaced the deliberately disabled, unconfigured "View on GitHub" primary CTA with a working "Get started" link to `/signup/`. A separate source-code link appears only when the actual project repository URL is configured.

## Checks completed

- Python suite: **183 passed** (147 prior tests plus 36 authentication/security/production-route cases).
- Frontend API-client suite: **8 passed**.
- Vite production build: **passed** for landing, signup, login, and dashboard.
- Built HTML asset and local navigation targets: **passed** for all four pages.
- Provider HTTP responses are simulated in tests. Google tests use cryptographically signed test ID tokens and actual Authlib validation, rejecting wrong signature, nonce, audience, issuer, expiry, and unverified email.
- Tests cover GitHub signup and returning login, PKCE parameters, invalid state, denied consent, forged/expired/revoked sessions, CSRF and Origin checks, HttpOnly/Secure cookies, unauthenticated direct URLs, and account-specific history/download isolation.
- One deprecation warning comes from the test-only `authlib.jose` signing helper; production authentication does not import that helper.

## Not completed / not claimed

- **Live Google consent and live GitHub consent:** not run. OAuth app client IDs/secrets and provider registrations were not supplied.
- **Public Python hosting:** not provisioned. The existing Sites publication serves only the frontend and cannot run the included Python OAuth/backend code. In that environment providers remain unavailable and the workspace does not render without a valid session response.
- **Browser visual and end-to-end QA:** unavailable in this environment. Existing simulated-response browser tests were updated for the authenticated bootstrap but were not executed.
- **Docker image build / hosted persistent-volume test:** not run. The deployment file and setup steps are supplied for a Python-capable host.

Use AUTH_SETUP.md to configure both providers, deploy the complete app under one HTTPS origin, and perform the live acceptance checklist. Credentials are never included in the ZIP.
