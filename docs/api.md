# Shikayat — API Reference

Base URL: `http://localhost:8000/api` (production: your deployed URL)

Auth: `Authorization: Bearer <JWT>` header on protected endpoints.

## Auth

### POST /auth/register
Public (rate-limited 10/min). Body:
```json
{ "name": "Ali", "email": "ali@x.pk", "password": "secret123", "role": "citizen", "ward": null }
```
`role`: citizen | officer | admin (ward required for officer). Returns `{access_token, user}` (201).

### POST /auth/login
Public (rate-limited 5/min). Body: `{ "email", "password" }` → `{access_token, user}` (200).

### GET /auth/me
→ current user.

## Categories

### GET /categories
Public. → `[{id, name, slug, icon, base_priority}]`

## Complaints

### POST /complaints (auth)
Body:
```json
{
  "title": "Broken street light on Main Road",
  "description": "Dark at night for two weeks…",
  "category_slug": "streetlights",
  "ward": "Gulshan Block 7",
  "area": "Gulshan-e-Iqbal",
  "severity": "high"
}
```
→ 201 with full complaint incl. ticket + priority.

### GET /complaints (auth)
Query: `?status=submitted&mine=true&category=streetlights`.
Role-scoped: officers see their queue; citizens see all (or own with `mine=true`); admins see all.

### GET /complaints/{id} (auth)
Full detail incl. `history` (status timeline) and `comments`.

### PATCH /complaints/{id} (auth)
Reporter/admin edits title/description while open.

### POST /complaints/{id}/transition (auth)
Body: `{ "to_status": "verified|rejected|in_progress|resolved|reopened", "note": "..." }`
Enforces the state machine → 200, or 409 (illegal move), 403 (wrong role).

### POST /complaints/{id}/assign (admin)
Body: `{ "officer_id": 5, "ward": "optional" }` → sets assignee, status → in_progress.

### POST /complaints/{id}/comments (auth)
Body: `{ "body": "Please fix soon" }` → 201 comment.

## Officers

### GET /officers/me/queue (officer)
Assigned complaints, open first, priority-sorted.

### GET /officers/{id}/complaints (admin)

## Admin

### GET /admin/officers (admin)
### GET /admin/stats (admin)
→ `{total, open, resolved, rejected, citizens, officers, by_status, by_category, resolve_rate}`

## Stats

### GET /stats/public
→ `{total_reported, resolved, by_category}` — no auth, powers the citizen dashboard.

## Health

### GET /health
→ `{status: "ok", app, version}`

## Error format

```json
{ "detail": "human-readable message" }
```
Validation errors: `{ "detail": [ { "loc": [...], "msg": "...", "type": "..." } ] }`

Status codes: 200 OK · 201 Created · 400 Bad input · 401 Unauthenticated ·
403 Forbidden role · 404 Not found · 409 State-machine conflict · 422 Validation · 429 Rate limited.
