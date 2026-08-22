# 📢 Shikayat (شکایت) — Civic Issue Tracker

> Report a broken streetlight, an open manhole, or a garbage mountain — then watch your complaint move from *submitted* to *resolved* with a paper trail nobody can lose.

Shikayat is a full-stack civic complaint tracker built for Pakistani cities. Citizens file issues in seconds, admins verify and assign them to the right ward officer, officers update progress, and the citizen sees every step — including the right to **reopen** a "resolved" complaint that wasn't actually fixed.

## ✨ Features

- 🏷️ **Ticket numbers & full history** — every complaint gets `SKT-2026-000042` and a timestamped status timeline with actor names
- 🔄 **State-machine-enforced workflow** — `submitted → verified → in_progress → resolved`, with `rejected` and citizen `reopened` (14-day window, max 3 reopens). Illegal jumps return HTTP 409 with a human-readable reason
- 🎯 **Computed priorities** — category base + severity + busy-area bonus (Saddar, Gulshan-e-Iqbal, Clifton…), so urgent issues float to the top
- 👥 **Three roles** — citizen / ward officer / admin, each with scoped views and permissions
- 💬 **Comments & resolution notes** on every complaint
- 📊 **Live stats** — city totals, resolve rate, per-category breakdown (public + admin)
- 📱 **Mobile-first dark SPA** — zero build step, works on any phone
- 🔐 **JWT + bcrypt auth**, rate-limited login, CORS allow-list, validated inputs

## 🛠 Tech Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI · Python 3.11 · SQLAlchemy 2.0 · Pydantic v2 |
| Auth | JWT (HS256, 24h) · bcrypt (12 rounds) · SlowAPI rate limits |
| Database | SQLite (dev, WAL) · PostgreSQL 16 (docker-compose) |
| Frontend | Vanilla JS · dark mobile-first SPA · no build step |
| Infra | Docker · docker-compose · Vercel-ready (serverless) |

## 📸 Screenshots

| Auth | Citizen dashboard | Report form | Admin |
|---|---|---|---|
| ![auth](https://static.teamily.ai/sites/24b16824-5a02-41eb-af47-c4372b8a0584/documents/auth/auth.png) | ![dashboard](https://static.teamily.ai/sites/24b16824-5a02-41eb-af47-c4372b8a0584/documents/dashboard/dashboard.png) | ![report](https://static.teamily.ai/sites/24b16824-5a02-41eb-af47-c4372b8a0584/documents/report/report.png) | ![admin](https://static.teamily.ai/sites/24b16824-5a02-41eb-af47-c4372b8a0584/documents/admin/admin.png) |

| Complaint detail |
|---|
| ![detail](https://static.teamily.ai/sites/24b16824-5a02-41eb-af47-c4372b8a0584/documents/detail/detail.png) |

## 🚀 Live Demo

<!-- LIVE-URL -->

> **Deployment status:** repo is Vercel-ready (`vercel.json` + `api/index.py`). Live URL will be inserted here once deployed.

## 📦 Installation

```bash
git clone https://github.com/mohdabrarbaloch-arch/day-16-shikayat.git
cd day-16-shikayat
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set SECRET_KEY
python seed.py              # categories + demo users
uvicorn app.main:app --reload --port 8000
```

Or with Docker (Postgres 16):

```bash
cp .env.example .env && docker compose up --build
```

Full setup, usage, and API docs live in [`docs/`](docs/):
[setup](docs/setup.md) · [usage](docs/usage.md) · [api](docs/api.md) · [architecture](ARCHITECTURE.md)

## 🔑 Demo Accounts

| Role | Email | Password |
|---|---|---|
| Admin | `admin@shikayat.pk` | `admin12345` |
| Officer | `officer@shikayat.pk` | `officer123` |
| Citizen | `citizen@shikayat.pk` | `citizen123` |

## ✅ Tests & Quality

- **47/47 tests passing** — state machine (transitions, priority, reopen window) + full API flow (auth, roles, lifecycle, scoping)
- **Ruff clean** (lint + format)
- Live smoke test verified every endpoint and the whole lifecycle end-to-end

```bash
pytest -q
ruff check . && ruff format --check .
```

## 🗺 Roadmap

- Image uploads (before/after photos) via S3
- SMS/WhatsApp notifications on status change
- Public read-only status page per ticket
- Geospatial indexing & map view for whole-city rollouts
- Urdu/Roman-Urdu UI toggle

## 📄 License

MIT — see [LICENSE](LICENSE).

---

Built on **Day 16** of the Autonomous AI Software Engineer 30-Day Challenge. 🚀
