# RepoLens Section 6 — Team Workspaces: Mac + Neon setup

## New behavior

- Owner and admin can create a one-use, 24-hour invitation. **Enter an email** to restrict the link to a verified Google/GitHub account's email. The application stores only a SHA-256 digest of the normalized email, not the address.
- Omitting the email retains the previous **unrestricted** invitation behavior: anyone signed in with the link can redeem it. The UI warns about this choice.
- Owner and admin can see pending invitations and revoke them. Neither the list nor the audit log shows raw invitation tokens or emails.
- Existing unredeemed links are preserved by the additive database migration.
- Roles (owner/admin/member), shared repository indexes, pinned citations, and **private per-user conversations** are retained.
- No outbound email is sent. Send the link to the recipient privately using your preferred channel. Automated email delivery would require a separately configured provider.

## 1. Preserve your working project and cloud database

Keep your working Section 5 folder. Create a Neon **recovery branch** or backup of your actual `RepoLens → production` branch **before** any migration. Never send `.env`, cookies, session secrets, Neon URLs or invite tokens to chat/GitHub.

Extract this ZIP into a NEW folder, for example `$HOME/Downloads/RepoLens 6`. Copy the existing private root `.env` from your working FastRAG/Section 5 folder into the new project. No new Gemini/GitHub/Google/Neon keys are needed.

## 2. Install from zero (new terminal opened in the new project root)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
npm test
cd ..
```

## 3. Apply the additive Neon migration

First verify your `.env` uses the intended *online* Neon database and you have a recovery branch. Do not paste the connection strings into terminal messages or chats.

```bash
python -m backend.database.schema_migrations status
python -m backend.database.schema_migrations upgrade
python -m backend.database.schema_migrations verify
```

Expected: `auth.current=auth_0004`, `app.current=app_0002`; for both `schema_valid: true` and `up_to_date: true`.

**Do not rerun SQLite → Neon transfer.** Section 6 adds only `workspace_invites.recipient_email_hash` (nullable); previous invitations and records remain in place. Downgrade is only allowed on empty disposable databases. Restore your backup/branch rather than downgrading a populated database.

## 4. Run your tests

```bash
python -m pytest -q tests/test_section6_tdd.py tests/test_section6_http_integration.py tests/test_section1_migrations.py
cd frontend
npm test
npx playwright install chromium
npm run test:browser -- e2e/section6_workspaces.spec.js
cd ..
```

The Playwright browser tests use mocked API data. HTTP integration tests use disposable SQLite stores with test-only OAuth identities; they do not exercise real provider authentication.

### Optional real-PostgreSQL concurrency test

Create a **separate Neon test branch and a disposable database named `repolens_section6_test`**. Set `REPOLENS_TEST_POSTGRES_URL` privately to that direct test database URL (not production `neondb`). Then run:

```bash
python -m pytest -q tests/test_section6_postgres_integration.py
```

This test refuses database names other than `repolens_section6_test` and refuses an identical production host/database combination. It inserts test rows and does not clean the test database. Delete the disposable Neon branch afterward. **Never point test URL at production**.

## 5. Start the website

Stop any older RepoLens launchers with Ctrl+C. Verify ports:

```bash
lsof -nP -iTCP:8000 -iTCP:5173 -sTCP:LISTEN
```

If occupied, inspect the process with `ps -p PID -o pid=,command=` and terminate only a known old RepoLens server (`kill -15 PID`). From the new project root:

```bash
node start.mjs
```

Open `http://127.0.0.1:5173/dashboard/` → **Knowledge Hub → Teams**.

## 6. Real website acceptance (two genuine accounts)

Use two independent browser profiles, not two tabs sharing one session.

1. **Owner:** Log in with your first Google or GitHub account. Create a workspace in Knowledge Hub → Teams. Select it.
2. **Owner:** In **Team invitations**, enter the second account's **verified** OAuth email and click **Create invitation link**. Copy it privately. Verify one pending restricted invitation is shown, but not its email or token.
3. **Wrong account (optional third account):** Attempt to use the link. It must be rejected **without consuming** the invitation.
4. **Intended member:** Open the link in another Chrome profile, log in with the specified verified account email, confirm joining. Owner must see the member in the list. Reusing the same invite must fail.
5. **Owner:** Share an indexed public repository from their own list. **Member:** Start a private chat from that shared revision and ask a question. Owner must NOT be able to read member's private chat. Shared pins, if explicitly made, can be seen by members.
6. **Owner:** Promote member to admin; check admin can create/revoke invites but cannot change the owner's role. Demote, then remove the member. Member must immediately lose workspace and shared-chat access.
7. **Owner:** Create another invitation, revoke it under Active invitations, verify its link no longer works. Expired links must fail as well.
8. Restart RepoLens. Confirm workspace membership, shared repository links and allowed pins persist in Neon, while removed members stay denied.

## 7. External setup you must complete

No new third-party service is necessary. Your assistance is needed for (a) taking a Neon recovery branch before migration, (b) supplying two real accounts with verified emails, and (c) Mac-side Playwright + optional Neon concurrency testing. Don't upload real invitation links or database credentials.

## Acceptance gates

Do not call Section 6 fully verified until the real OAuth accounts, current Neon schema, browser tests, and shared-index/privacy behavior all pass. Offline tests do not prove the production provider configuration works.
