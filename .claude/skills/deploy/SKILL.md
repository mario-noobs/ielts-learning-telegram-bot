---
description: Deploy the IELTS bot to the production VPS, or rollback a bad deploy
match:
  - deploy the bot
  - ship to production
  - deploy to remote
  - rollback the deploy
  - revert the deploy
---

# Deploy IELTS Bot

## Prerequisites

- SSH access to the production VPS (key-based authentication)
- Host: the IP/hostname stored in GitHub Actions secret `SSH_HOST`
- User: the SSH user stored in GitHub Actions secret `SSH_USER`
- The VPS must have `.env` and `firebase_credentials.json` already in place at `/home/ielts/ielts-bot/`
- The `ielts` user must have passwordless `sudo` permission for `systemctl restart ielts-bot` and `systemctl is-active ielts-bot`

## Initial Server Setup (one-time)

Run these commands on a fresh Ubuntu 22.04+ VPS as root:

```bash
# 1. Create dedicated user
adduser --disabled-password --gecos "" ielts
usermod -aG sudo ielts

# 2. Allow passwordless sudo for systemctl commands only
echo 'ielts ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart ielts-bot, /usr/bin/systemctl is-active ielts-bot' \
  > /etc/sudoers.d/ielts-bot
chmod 440 /etc/sudoers.d/ielts-bot

# 3. Set up SSH key for the ielts user
su - ielts
mkdir -p ~/.ssh && chmod 700 ~/.ssh
# Paste the public key (whose private key is in GitHub Actions secret SSH_PRIVATE_KEY):
echo "ssh-ed25519 AAAA... deploy@github-actions" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# 4. Clone the repo
cd /home/ielts
git clone https://github.com/mario-noobs/ielts-learning-telegram-bot.git ielts-bot
cd ielts-bot

# 5. Create venv and install dependencies
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# 6. Place secrets on the host (never committed to git)
#    Copy .env and firebase_credentials.json into /home/ielts/ielts-bot/
#    Edit .env with your TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, etc.

# 7. Create the systemd service unit
sudo tee /etc/systemd/system/ielts-bot.service > /dev/null <<'EOF'
[Unit]
Description=IELTS Telegram Bot
After=network.target

[Service]
Type=simple
User=ielts
WorkingDirectory=/home/ielts/ielts-bot
EnvironmentFile=/home/ielts/ielts-bot/.env
ExecStart=/home/ielts/ielts-bot/venv/bin/python main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 8. Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable ielts-bot
sudo systemctl start ielts-bot

# 9. Verify
systemctl is-active ielts-bot    # should print "active"
journalctl -u ielts-bot -f       # tail logs to confirm startup
```

## Deploy Procedure

Deploy is **manual over SSH**. The production host sits on a private LAN and isn't reachable from GitHub-hosted runners, so the workflow at `.github/workflows/deploy.yml` is configured as `workflow_dispatch`-only and is currently unused. It will become the auto-deploy path once we move to a public VPS or add a self-hosted runner.

```bash
ssh ielts@<host>
cd /home/ielts/ielts-bot
git pull origin main
./venv/bin/pip install -r requirements.txt --quiet
sudo systemctl restart ielts-bot
```

Then verify with the health check below.

## Rollback Procedure

If a deploy breaks the bot, roll back to the last known good commit:

```bash
ssh ielts@<host>
cd /home/ielts/ielts-bot

# 1. Find the last good commit
git log --oneline -5

# 2. Check out that commit (detached HEAD is fine for rollback)
git checkout <good-sha>

# 3. Re-install dependencies in case they changed
./venv/bin/pip install -r requirements.txt --quiet

# 4. Restart the service
sudo systemctl restart ielts-bot

# 5. Verify
sleep 5
systemctl is-active ielts-bot
journalctl -u ielts-bot --since "2 minutes ago" --no-pager
```

After stabilizing, fix the issue on a branch, merge to `main`, then on the host run `git checkout main && git pull origin main` to get back on the main branch.

## Health Check

```bash
# Is the process running?
systemctl is-active ielts-bot

# Recent logs (last 5 minutes)
journalctl -u ielts-bot --since "5 minutes ago" --no-pager

# Full service status
systemctl status ielts-bot
```

A healthy deploy shows `active` from `is-active` and no Python tracebacks in the journal output.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `inactive (dead)` after restart | Import error or missing dependency | `journalctl -u ielts-bot -n 50 --no-pager` to find the traceback; fix and re-deploy |
| `activating (auto-restart)` looping | Crash loop — process starts then dies | Check logs; common causes: missing `.env` vars, bad `firebase_credentials.json`, network issues |
| `git pull` fails with merge conflicts | Someone edited files directly on the host | `git stash` or `git reset --hard origin/main` (safe because no host-local code changes should exist) |
| `pip install` fails | Network issue or broken package | Retry; if persistent, SSH in and run pip manually to see the full error |
| Service won't start after OS reboot | systemd unit not enabled | `sudo systemctl enable ielts-bot` then `sudo systemctl start ielts-bot` |
