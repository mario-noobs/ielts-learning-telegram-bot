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

## Boundary with Firestore

Postgres becomes authoritative for the user core doc only after US-M8.2 ships the cutover PR. Until then, Firestore is the source of truth and Postgres exists for schema validation + M11 development. After cutover, services must call the Postgres user_repo (`services/repositories/postgres/user_repo.py`, M8.2). Subcollections continue to use the existing Firestore repos in `services/repositories/firestore/`.
