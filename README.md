# Telegram Bot: Garage Service

A minimal Telegram bot (aiogram v3) with two buttons: "Принять машину в ремонт" and "Гараж".

## Setup

1. Create virtual environment and install dependencies:

```bash
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
```

2. Configure environment:

```bash
cp .env.example .env
# Edit .env and set BOT_TOKEN
```

## Run

```bash
./.venv/bin/python -m bot.main
```

If running on Linux, `uvloop` will be used automatically if installed.
