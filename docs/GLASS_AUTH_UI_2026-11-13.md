# RepoLens glass login/sign-up UI (2026-11-13)

## Integration

- `frontend/src/components/ui/sign-up.jsx`: reusable React AuthComponent, adapted from the provided sign-up mockup.
- `frontend/src/components/ui/auth.css`: scoped near-black charcoal/dark-grey/soft-blue palette, muted glass controls, subtle animated background and 3D example source window.
- `frontend/src/components/ui/authFlow.mjs`: safe OAuth provider whitelist, validation, allowlisted join redirects and error copy.
- `frontend/src/auth.jsx`: dedicated React entry point for both routes.
- `frontend/login/index.html`, `frontend/signup/index.html`: HTML pages that mount the component.

The source project uses JavaScript/JSX and CSS, **not** Tailwind, shadcn or TypeScript. The new component is adapted to that existing stack instead of converting the whole project or adding unneeded packages. Its name and folder follow the requested component pattern: `src/components/ui/sign-up.jsx`.

## Important authentication decision

The supplied demo has a local email/password wizard that always ends in a fake success animation. RepoLens uses Google and GitHub OAuth and has no compatible email/password registration backend. The new UI **does not** invent registration success or collect/store passwords. Google and GitHub remain disabled until `/api/auth/providers` reports them available; providers redirect to the existing `/api/auth/login/{provider}` routes. Valid `/join?token=...` invitations remain supported. `/api/auth/me` is still used to restore an existing session. The UI makes no changes to auth server code.

## Colours

- Background `#121416`
- Cards `#222528`
- Button/active blue `#28547A`
- Gentle highlight blue `#91BDE2`
- Primary text `#F5F5F3`
- Sand is deliberately omitted from the auth screens.

## Verify from the project folder on macOS

```bash
cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
npx playwright test e2e/auth_theme.spec.js
npm run test:browser
cd ..
node start.mjs
```

Open `/signup/` and `/login/`, confirm each provider's actual OAuth setup, and check successful callbacks manually. Browser tests mock OAuth provider availability and cannot confirm an external provider's consent screen.

## Scope

Only public signup/login routes and their tests have been restyled. The cinematic 3D landing page, dashboard, backend and database migrations remain unchanged.
