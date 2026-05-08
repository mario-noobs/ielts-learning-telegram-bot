# Postgres

Self-hosted Postgres backs the user core doc + admin entities. Per-user activity subcollections (vocabulary, quiz_history, writing_history, daily_words, listening_history, reading_sessions, daily_plans, progress_snapshots, progress_recommendations, quiz_sessions) stay in Firestore. Groups + challenges stay in Firestore. See ADR-M8-1 (revised) for the reasoning.

## Local dev

`make dev` brings up a `postgres:16-alpine` container under the `dev` profile alongside the Firebase emulators, runs `alembic upgrade head`, then starts the API and web. Connection string: `postgresql+asyncpg://ielts:dev@localhost:5432/ielts`.

To run only Postgres: `make postgres`. To stop it: `make postgres-down`.

To inspect the running schema:

```bash
docker exec ielts-bot-postgres-1 psql -U ielts -d ielts -c '\d users'
```

## Production setup (one-time, on the VPS)

```bash
sudo apt install postgresql-16 postgresql-contrib
sudo systemctl enable --now postgresql

# Create role + database. The createuser prompt sets the password.
sudo -u postgres createuser --pwprompt ielts
sudo -u postgres createdb -O ielts ielts

# Allow the local app to connect via password on 127.0.0.1.
sudo $EDITOR /etc/postgresql/16/main/pg_hba.conf
# Add or amend:  host  ielts  ielts  127.0.0.1/32  md5
sudo systemctl reload postgresql

# Wire the app: add to /home/ielts/ielts-bot/.env
DATABASE_URL=postgresql+asyncpg://ielts:<password>@127.0.0.1:5432/ielts

# Apply schema
cd /home/ielts/ielts-bot && ./venv/bin/alembic upgrade head

# Verify
sudo -u ielts psql -d ielts -c '\dt'
# users + alembic_version should be listed
```

For routine deploys, rollback, and on-call troubleshooting, the operator's runbook lives at `.claude/skills/deploy/SKILL.md` (gitignored — per-machine).

## Migrations

Alembic root: `migrations/`. Config: `alembic.ini`. Env: `migrations/env.py` reads `config.DATABASE_URL` so a single `.env` drives both the app and migrations.

```bash
# Apply pending migrations (also runs as part of make seed / make dev)
alembic upgrade head

# Roll back the latest migration
alembic downgrade -1

# Generate a new migration from current model diffs
alembic revision --autogenerate -m "short description"
# Review the generated file by hand — autogenerate misses index renames,
# server-side defaults, and check constraints. Adjust before committing.

# Drop everything (local dev only)
alembic downgrade base
```

## Schema scope

The `users` table mirrors `services/repositories/dtos.py:UserDoc` plus admin fields owned by M11:

- `role` — `user` / `team_admin` / `org_admin` / `platform_admin`
- `plan` — `free` / `personal_pro` / `team_member` / `org_member`
- `plan_expires_at` — date the plan expires
- `team_id`, `org_id` — denormalized membership pointers; FK constraints land in M11.1's migration once the `teams` / `orgs` tables exist
- `quota_override` — admin override of plan default daily quota
- `last_active_date`, `signup_cohort` — drive DAU/MAU + cohort retention

The `auth_uid` column has a UNIQUE constraint, so `get_user_by_auth_uid` is a single indexed `SELECT * FROM users WHERE auth_uid = $1` — no separate `auth_mapping` table.

## Admin schema (M11.1)

Migration `0002_admin_baseline.py` adds the admin data layer. All tables are Postgres-only (no Firestore mirror).

| Table | Purpose | Notes |
|---|---|---|
| `plans` | Subscription tier definitions | text PK; seeded with `free`, `personal_pro`, `team_member`, `org_member`. Carries `daily_ai_quota`, `monthly_ai_quota`, `max_team_seats`, `features` (JSONB list) |
| `teams` | Team entity | uuid PK (`gen_random_uuid()`), FK `plan_id → plans.id`, `seat_limit` |
| `team_members` | Team membership | composite PK `(team_id, user_uid)`; ON DELETE CASCADE; CHECK constraint `role IN ('member', 'admin')` |
| `orgs` | Org entity | uuid PK, FK `plan_id → plans.id` |
| `org_admins` | Org admin assignment | composite PK; ON DELETE CASCADE |
| `org_teams` | Org → team links | composite PK; ON DELETE CASCADE on both sides |
| `audit_log` | Append-only admin action log | bigserial PK; JSONB `before`/`after`; indexes on actor/target/created_at |
| `ai_usage` | Per-user-per-day-per-feature quota counter | composite PK `(user_uid, date, feature)`; primitive for M11.2's quota enforcement (`INSERT … ON CONFLICT DO UPDATE … RETURNING count`) |
| `platform_metrics` | Daily snapshot for the dashboard | date PK; JSONB `plan_distribution`; written by the cron in M11.5 |

**FK constraints added on `users`** by the same migration: `users.plan → plans.id`, `users.team_id → teams.id`, `users.org_id → orgs.id`. `users.team_id` and `users.org_id` were converted from `text` to `uuid` so the FKs resolve.

Postgres repos for each admin table live in `services/repositories/postgres/{plan_repo,team_repo,org_repo,audit_repo,ai_usage_repo,metrics_repo}.py`. Lazy-singleton factories live in `services/repositories/__init__.py` (`get_plan_repo`, `get_team_repo`, etc.).

## Admin CLI (M11.2)

`scripts/admin.py` is the chicken-and-egg first-admin bootstrap. The `/admin/*` UI gates on `role == 'platform_admin'` but no user has that role until the CLI sets it.

```bash
# Find the auth_uid of the human you want as the first admin.
psql postgresql://ielts:dev@localhost:5432/ielts \
  -c "SELECT id, name, email, auth_uid FROM users WHERE email = 'them@example.com'"

# Grant
python scripts/admin.py grant-admin --uid <auth_uid>

# Confirm
python scripts/admin.py list-admins
```

Subcommands:

- `grant-admin --uid <auth_uid>` — set `role = 'platform_admin'`
- `revoke-admin --uid <auth_uid>` — set `role = 'user'`
- `set-plan --uid <auth_uid> --plan <id> [--expires YYYY-MM-DD]` — assign a plan + optional expiry. FK rejects unknown plan ids.
- `list-admins` — print every user with `role != 'user'` as JSON

Every mutation writes one `audit_log` row (`actor_uid='cli:<os-user>'`).

## Admin field backfill (M11.2)

`scripts/backfill_admin_fields.py` populates `last_active_date` + `signup_cohort` for rows where they're NULL — these are the inputs to the M11.5 dashboard's DAU/MAU + cohort retention.

```bash
python scripts/backfill_admin_fields.py
```

Idempotent. Computes `last_active_date := COALESCE(last_active::date, created_at::date)` and `signup_cohort := to_char(created_at, 'YYYY-MM')` server-side. Re-running on a clean table reports 0 rows updated.

Run after every M8.2 user backfill so the new admin columns are populated.

## Boundary with Firestore

US-M8.6 (closes #191) flipped `services/repositories/__init__.py:get_user_repo()` to return `PostgresUserRepo`. Postgres is now authoritative for the user core doc — `id`, `auth_uid`, `email`, `name`, `role`, `plan`, `team_id`, `org_id`, `quota_override`, `last_active_date`, `signup_cohort`, and the aggregate counters `total_words` / `total_quizzes` / `total_correct` / `streak`.

Subcollections continue to live in Firestore (`vocabulary`, `quiz_history`, `writing_history`, `daily_words`, `listening_history`, `reading_sessions`, `daily_plans`, `progress_snapshots`, `progress_recommendations`, `quiz_sessions`). Their repos in `services/repositories/firestore/` write the subcollection doc and then call `get_user_repo().increment_counters(uid, …)` to bump aggregate counters in the authoritative store. Cross-store atomicity is impossible at this seam; the counter increment runs after the Firestore subcollection write commits and the divergence window is bounded by a single RPC.

### Cutover sequence (US-M8.6, ops)

1. Backfill: `python scripts/backfill_users_to_postgres.py` (US-M8.2).
2. Verify: `python scripts/verify_user_migration.py` — exits 0 on parity.
3. Merge the cutover PR + deploy.
4. 24h soak window with `user_repo_cutover_active=postgres` log line confirmed in API + bot startup logs.
5. Tighten production Firestore security rules so `users/` and `auth_mapping/` collections are read-only (production rules are managed outside the repo's `firestore.rules` emulator file). Deploy via `firebase deploy --only firestore:rules --project <prod>`.
6. After 30 days with no rollback, delete the `users/` and `auth_mapping/` Firestore collections (US-M8.8).

### Rollback

Revert the cutover PR and redeploy. `get_user_repo()` returns `FirestoreUserRepo` again. All signups since cutover are still readable because the same user `id` exists in both stores from the backfill step. Firestore archive is preserved through the 30-day window, so there's no data loss; only counter writes that fired during the soak window need reconciliation (run the backfill script in reverse).

### Auth mapping retired

Pre-cutover, web auth uid → user_id used the `auth_mapping/{auth_uid}` Firestore collection. Post-cutover, `PostgresUserRepo.get_by_auth_uid` does a single indexed `SELECT` against the UNIQUE `auth_uid` column from US-M8.1. The `auth_mapping/` collection is part of the read-only archive and will be deleted with US-M8.8.

## Identity merge (US-M12.1)

Until US-M12.1 the `/link` flow for a web-first user (already had `web_xxx` row) was unreachable: the bare `UPDATE users SET auth_uid=$1 WHERE id=$telegram_id` was rejected by the UNIQUE `auth_uid` constraint added in US-M8.1. US-M12.1 detects the web-first case and runs an atomic merge instead.

### Precondition

Merge fires when **both** are true:
1. `existing = get_user_by_auth_uid(auth_uid)` returns a row with `id` starting `web_`.
2. `telegram_user = get_user(telegram_id)` returns a row with `auth_uid IS NULL`.

Otherwise the route falls back to the US-M8.6 `link_telegram_to_auth` UPDATE.

### Field merge rules (Postgres `users` row)

Inside one `s.begin()` block with `SELECT … FOR UPDATE` on both rows. The surviving row is the Telegram row (`id=str(telegram_id)`); the `web_xxx` row is `DELETE`d at the end so the UNIQUE `auth_uid` constraint is satisfied.

| Field | Rule |
|---|---|
| `auth_uid` | from `web_xxx` |
| `email`, `name`, `username` | non-empty wins; tie-break to `web_xxx` (Google profile) |
| `target_band` | `web_xxx`'s if Telegram is at default 7.0; else keep Telegram's |
| `topics` | union, deduped, max 5 |
| `streak` | `MAX(web, tg)` |
| `last_active` | `GREATEST(web, tg)` |
| `created_at` | `LEAST(web, tg)` — preserve oldest signup for cohort math |
| `total_words` | sum, then **rewritten** as target vocab subcollection size after dedupe |
| `total_quizzes`, `total_correct`, `challenge_wins` | summed |
| `role` | max-privilege via `api/permissions.py:ROLE_LEVELS` |
| `plan` + `plan_expires_at` | `web_xxx`'s if non-`free`, else Telegram's |
| `team_id`, `org_id`, `quota_override` | non-null wins |
| `signup_cohort`, `last_active_date` | recomputed from merged `created_at` / `last_active` |

### Subcollection merge (Firestore)

In-scope (4 collections):

| Subcollection | Rule |
|---|---|
| `vocabulary` | dedupe by lowercased `word`; on duplicate keep entry with greater `srs_reps`; tie-break to Telegram |
| `quiz_history` | append-only union (each entry is a distinct attempt) |
| `writing_history` | append-only union |
| `daily_words` | keyed by `date_str`; on conflict, **Telegram doc wins** (bot is the originator) |

Out-of-scope (intentionally **not migrated**): `listening_history`, `reading_sessions`, `daily_plans`, `progress_snapshots`, `progress_recommendations`, `quiz_sessions`. Either ephemeral, regenerable, or cache.

### Order + atomicity

1. Read both Postgres rows (snapshot for the merge dict).
2. Stream the 4 in-scope Firestore subcollections from `users/{web_xxx}/<sub>` into `users/{telegram_id}/<sub>` per the table above.
3. Recompute `total_words` from the deduped target vocab (avoids double-count from summed counters).
4. Postgres txn: `UPDATE target` + `DELETE source`. Commit.
5. Best-effort delete of `users/{web_xxx}/<sub>` docs. Failure logged, not raised.
6. Audit row `event_type='user.merged'` + structlog `user.merged` event with counts.

Step 2 failure → no Postgres mutation → 500 `auth.link.merge_failed`, both rows still exist.

Step 4 failure after step 2 succeeded → subcollection docs are now in both stores. **Idempotent retry** — re-running produces the same end state because vocab dedupe is keyed on the word and quiz/writing/daily_words `set(...)` overwrites are no-ops.

## Identity unlink (US-M12.1)

The inverse of link. Detaches Firebase Auth from a Telegram account without destroying any data.

- **Web** — `DELETE /api/v1/users/link`. Auth: Firebase ID token. Rejects `web_xxx` rows with 409 `auth.link.web_only_account`; otherwise clears `auth_uid`.
- **Bot** — `/unlink` command, private DM only. Same op.

Postgres operation: `SELECT … FOR UPDATE` on the row, capture previous `auth_uid`, set it to `NULL`. Idempotent — already-unlinked rows are a no-op and write no audit row.

**Subcollections, counters, plan/role/team_id/org_id stay on the Telegram row.** A subsequent web sign-in with the same Google account creates a fresh empty `web_xxx` via the dashboard auto-create. Re-link via `/link` runs the merge path and absorbs the empty `web_xxx` back into the Telegram row.

Audit: `event_type='user.unlinked'`, `actor_uid='self:web'` or `'self:bot'`.
