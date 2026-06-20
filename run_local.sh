#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env. Add TELEGRAM_BOT_TOKEN and run again."
  exit 1
fi

mkdir -p data
exec python bot.py
