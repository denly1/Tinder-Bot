#!/usr/bin/env bash
set -euo pipefail
APP_DIR=/opt/tin-bot
VENV_DIR="$APP_DIR/venv"
LOG_DIR=/var/log/tin-bot

if [ ! -d "$APP_DIR/.git" ]; then
  echo "App not cloned at $APP_DIR" >&2
  exit 1
fi

cd "$APP_DIR"

# Pull latest
git fetch --all
git reset --hard origin/main

# Python venv
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install -U pip
"$VENV_DIR/bin/pip" install -r requirements.txt

# Run migrations
export $(grep -v '^#' /etc/tin-bot.env | xargs)
"$VENV_DIR/bin/alembic" upgrade head

# Restart service
sudo systemctl restart tin-bot
echo "Deploy finished"
