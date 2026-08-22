# Shikayat — Setup Guide

## Local development

```bash
# 1. Clone & enter
git clone https://github.com/mohdabrarbaloch-arch/day-16-shikayat.git
cd day-16-shikayat

# 2. Python 3.11+ virtual env
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
#   → set SECRET_KEY to a long random value

# 5. Seed demo data (categories + demo users)
python seed.py

# 6. Run
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 — the SPA loads at the root. Interactive API docs
at http://localhost:8000/docs.

## Docker (PostgreSQL 16)

```bash
cp .env.example .env          # set SECRET_KEY
docker compose up --build
```

The API is at http://localhost:8000, Postgres on :5432. The compose file
auto-runs `seed.py` on first boot.

## Tests & linting

```bash
pytest -q                 # 47 tests — state machine + full API flow
ruff check .              # must pass clean
ruff format --check .     # must pass clean
```

## Demo accounts (created by seed.py)

| Role | Email | Password |
|---|---|---|
| Admin | admin@shikayat.pk | admin12345 |
| Officer | officer@shikayat.pk | officer123 |
| Officer (Saddar) | saddar@shikayat.pk | officer123 |
| Citizen | citizen@shikayat.pk | citizen123 |

## Deploying to Vercel

The repo is Vercel-ready:

1. Push to GitHub, then import the repo at https://vercel.com/new
2. Add environment variables: `SECRET_KEY` (required), `DATABASE_URL` (optional —
   defaults to ephemeral SQLite in /tmp)
3. Deploy. Framework preset: Other; build command: none; output: default.

> Note: SQLite on Vercel is ephemeral (per-instance /tmp). For a persistent
> deployment point `DATABASE_URL` at a hosted Postgres (Neon/Supabase/RDS).
