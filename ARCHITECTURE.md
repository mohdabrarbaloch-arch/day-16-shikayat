# Shikayat (شکایت) — Architecture

Shikayat is a civic issue & complaint tracker for Pakistani cities. A citizen reports
a broken streetlight or an open manhole from their phone; an admin assigns it to the
right municipal ward; the ward officer updates progress; the citizen sees every step
and can reopen a complaint that wasn't really fixed.

## Why this exists

In most Pakistani cities the "complaint" channel is a Facebook post or a phone call
that nobody logs. There is no ticket number, no owner, no SLA, no history. Shikayat
gives every complaint a lifecycle, an assignee, and a public-ish trail — the same
shape as FixMyStreet in the UK, but built for local reality (wards, municipal
departments, Urdu-first naming).

## System diagram

```
                    ┌──────────────────────────────────────────┐
                    │              Browser (SPA)                │
                    │  citizen / admin / officer dashboards     │
                    └──────────────────┬───────────────────────┘
                                       │ HTTPS (JSON)
                                       ▼
                    ┌──────────────────────────────────────────┐
                    │              FastAPI (app/)               │
                    │  routers: auth · categories · complaints │
                    │           officers · admin · stats       │
                    │  core/state_machine.py  (lifecycle)      │
                    │  security.py (JWT+bcrypt+ratelimit)      │
                    └──────────────────┬───────────────────────┘
                                       │ SQLAlchemy 2.0 ORM
                                       ▼
                    ┌──────────────────────────────────────────┐
                    │   SQLite (dev, WAL) / PostgreSQL 16      │
                    │   users · categories · complaints        │
                    │   status_history · comments              │
                    └──────────────────────────────────────────┘
```

## Complaint state machine

```
                     ┌──────────┐   verify    ┌──────────┐   assign   ┌────────────┐
   citizen submits   │          │ ──────────▶ │          │ ─────────▶ │            │
   ─────────────────▶│ submitted│             │ verified │            │ in_progress│
                     │          │ ◀────────── │          │            │            │
                     └──────────┘   reject    └──────────┘            └─────┬──────┘
                          │                                                 │ resolve
                          │ reject/duplicate                               ▼
                          ▼                                          ┌────────────┐
                     ┌──────────┐                                    │  resolved  │
                     │ rejected │                                    └─────┬──────┘
                     └──────────┘                                          │ citizen
                           ▲                                                │ reopens
                           │ reject                                          ▼
                           └───────────────────────────────────────┌────────────┐
                                                                    │  reopened  │
                                                                    └────────────┘
```

Rules enforced by `app/core/state_machine.py`:

- `submitted` → `verified` (admin) or `rejected` (admin, with reason)
- `verified` → `in_progress` (admin assigns a ward officer) or `rejected`
- `in_progress` → `resolved` (officer, with resolution note) or `rejected` (admin)
- `resolved` → `reopened` (the *reporter* can reopen within 14 days — "it's not fixed")
- `reopened` → `in_progress` (admin re-assigns) — no unlimited loops; a complaint can
  be reopened at most 3 times
- Only the reporter, the assignee, and admins may act on a complaint. Illegal moves
  return HTTP 409 with a human-readable reason.

## Priority scoring

A complaint's priority is computed, not typed:

```
priority = base(category) + severity_bonus(sev) + area_bonus
  area_bonus: 0 normal / 5 busy (e.g. "Saddar", "Gulshan-e-Iqbal") / 3 school
```

Scoring lives in the engine and is unit-tested.

## Data model (core tables)

| Table | Purpose |
|---|---|
| users | id, name, email, password_hash, role (citizen/admin/officer), ward |
| categories | id, name, slug, base_priority |
| complaints | id, ticket (SKT-000123), title, description, category_id, reporter_id, assignee_id, ward, area, severity (low/medium/high), status, priority, resolved_note, reopen_count, timestamps |
| status_history | id, complaint_id, from_status, to_status, actor_id, note, created_at |
| comments | id, complaint_id, author_id, body, created_at |

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI 0.115 + Pydantic v2 + Uvicorn |
| ORM | SQLAlchemy 2.0 (declarative, typed) |
| DB | SQLite (WAL, dev) · PostgreSQL 16 (docker-compose) |
| Auth | JWT (HS256, 24h) + bcrypt (12 rounds) + slowapi rate limits |
| Frontend | Vanilla JS mobile-first dark SPA, zero build step |
| Infra | Docker · docker-compose · Vercel-ready (vercel.json + api/index.py) |

## Security

- Secrets only in env; `SECRET_KEY` required (`.env.example` documents all vars)
- CORS allow-list; login rate-limited (5/min per IP, SlowAPI)
- Pydantic validation on every input; owner/role checks in dependencies
- Foreign access to a complaint returns 404 (not 403) to avoid leaking existence
- Passwords hashed with bcrypt; JWT contains only `sub` + `role`

## Scaling notes

- Stateless API → horizontal scaling behind a load balancer is trivial
- SQLite is dev-only; production uses Postgres (WAL, indexes on status/ward/ticket)
- Ticket numbers are generated per-year-sequence; collision-safe under concurrency
- For a full city rollout, add: image upload (S3), SMS/WhatsApp notifications,
  a public read-only status page, and a geospatial index on complaint coordinates.

## Local run

```bash
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Tests: `pytest -q` · Lint: `ruff check . && ruff format --check .`
