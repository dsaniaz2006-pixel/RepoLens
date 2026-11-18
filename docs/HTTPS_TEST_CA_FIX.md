# RepoLens C2 HTTPS test CA fix (Nov 14, 2026)

Cause: Node.js Playwright request clients reject the trusted local mkcert certificate when their process does not load the macOS Keychain or mkcert CA. Chrome rendering worked, but APIRequestContext returned `unable to verify the first certificate`.

Solution: `scripts/verify_local_https_browser.mjs` obtains `mkcert -CAROOT`, checks `rootCA.pem`, launches Playwright with `NODE_EXTRA_CA_CERTS` and `NODE_USE_SYSTEM_CA=1`, and leaves TLS validation fully enabled. It refuses to run without the CA and removes any insecure `NODE_TLS_REJECT_UNAUTHORIZED` override from its child environment. It does not distribute certificate material.

Run from project root: `node scripts/verify_local_https_browser.mjs`.
Or from frontend: `npm run test:browser:https`.
Or all gates: `bash scripts/verify_predeploy.sh`.

If the tests still fail, first run `mkcert -install && node scripts/setup_local_https.mjs`, close any older RepoLens servers, then retry. Do not share `rootCA-key.pem`.
