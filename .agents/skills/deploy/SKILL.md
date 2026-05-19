---
name: deploy
description: Use for production deploys, server setup, rollback, and troubleshooting. Production host is private LAN; deploys are manual.
---

# Deploy

## Purpose

Stand up and update the IELTS production host (private LAN, `192.168.x.x`). All deploys are manual — no GitHub-runner reachability.

## When to Use

Server provisioning, every release to production, rollback, on-call troubleshooting.

## Instructions — routine deploy

1. `ssh ielts@<host>`
2. `cd /home/ielts/ielts-bot`
3. `git pull origin main`
4. `./venv/bin/pip install -r requirements.txt --quiet`
5. `./venv/bin/alembic upgrade head` (skip if no new migrations)
6. `sudo systemctl restart ielts-bot`
7. `journalctl -u ielts-bot -n 50` to confirm clean start

## Instructions — Postgres provisioning (first time)

Self-hosted on the same VPS as the bot service. Per ADR-M8-1.

1. `sudo apt install postgresql-16 postgresql-contrib`
2. `sudo systemctl enable --now postgresql`
3. As postgres OS user, create the role and database:
   ```bash
   sudo -u postgres createuser --pwprompt ielts
   sudo -u postgres createdb -O ielts ielts
   ```
4. Edit `/etc/postgresql/16/main/pg_hba.conf` to allow the local app to connect via `md5` on `127.0.0.1/32`. Reload: `sudo systemctl reload postgresql`.
5. Add `DATABASE_URL=postgresql+asyncpg://ielts:<password>@127.0.0.1:5432/ielts` to `/home/ielts/ielts-bot/.env`.
6. Run `./venv/bin/alembic upgrade head` from the project directory.
7. Verify: `sudo -u ielts psql -d ielts -c '\dt'` lists `users` and `alembic_version`.

## Instructions — admin bootstrap (first platform_admin)

Required after every fresh deploy and once after the M8.2 user-data
backfill lands in prod. Without it the `/admin/*` UI is reachable
by no one.

```bash
# Find the Firebase auth_uid of the human you want as the first
# admin. They must already be a registered user (web signup or
# linked Telegram) so users.auth_uid is populated.
sudo -u ielts psql -d ielts -c \
  "SELECT id, name, email, auth_uid FROM users WHERE email = '<them>'"

# Grant
cd /home/ielts/ielts-bot
./venv/bin/python scripts/admin.py grant-admin --uid <auth_uid>

# Confirm
./venv/bin/python scripts/admin.py list-admins
```

`scripts/admin.py` also exposes `revoke-admin`, `set-plan --uid X
--plan personal_pro [--expires 2027-01-01]`, and `list-admins`.
Every mutation writes an `audit_log` row (actor=`cli:<os-user>`).

## Instructions — admin field backfill

After M8.2's `scripts/backfill_users_to_postgres.py` populates
the `users` table, the new admin columns (`last_active_date`,
`signup_cohort`) are NULL on every backfilled row. The M11.5
admin dashboard reads those columns directly, so run:

```bash
cd /home/ielts/ielts-bot
./venv/bin/python scripts/backfill_admin_fields.py
```

Idempotent — only touches rows where one of the two fields is
NULL. Safe to re-run whenever new users arrive without those
fields populated by application code.

## Instructions — backups

Owned by US-M8.5. Until that lands, take a manual `pg_dump` before any risky migration:
```bash
pg_dump -Fc -U ielts ielts > /home/ielts/backups/$(date +%F).pgdump
```

## Instructions — rollback

- **Bad code**: `git reset --hard <prev-sha>` + `pip install -r requirements.txt --quiet` + `systemctl restart ielts-bot`.
- **Bad migration**: `./venv/bin/alembic downgrade -1` then redeploy the prior code. If the migration is irreversible, restore from the most recent `pg_dump`.
- **Hung process**: `systemctl restart ielts-bot`; if that hangs, `systemctl reset-failed ielts-bot && systemctl start ielts-bot`.

## Heuristics

- Never deploy without `journalctl -u ielts-bot -n 50` confirming startup.
- Never run `alembic upgrade head` without a fresh `pg_dump` once production has live data (post-launch).
- Never `git pull` and skip `pip install` — silent dependency drift.
- The host is on `192.168.x.x`; GitHub-hosted runners can't reach it. Don't try to wire push-triggered auto-deploy until we move to a public VPS.

## Examples

- Routine: `ssh ielts@host`, pull, pip install, alembic upgrade, restart, tail journal.
- First Postgres setup: apt install → createuser/createdb → pg_hba.conf → .env DATABASE_URL → alembic upgrade head → verify with `\dt`.
- First admin: `psql` to find the auth_uid → `python scripts/admin.py grant-admin --uid X` → `list-admins` to confirm.
- Migration regret: `alembic downgrade -1`, restart, monitor for 10 minutes.
