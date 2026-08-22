# Shikayat — Usage Guide

## Roles

| Role | What they can do |
|---|---|
| **Citizen** | File complaints, track them, comment, reopen a "resolved" complaint that isn't actually fixed |
| **Officer** | See only their assigned queue, mark work resolved with a note |
| **Admin** | Verify/reject complaints, assign officers, see city-wide stats |

## Workflow

1. **Citizen files a complaint** — picks a category (Roads, Streetlights, Garbage,
   Water, Sewage…), describes the issue, adds ward/area and severity. Every
   complaint gets a ticket number (SKT-2026-000001) and a computed priority.
2. **Admin verifies** — real complaint → `verified`; duplicate/spam → `rejected`
   with a reason.
3. **Admin assigns** — picks a ward officer → status becomes `in_progress`.
4. **Officer resolves** — completes the work and writes a resolution note.
5. **Citizen sees the trail** — every status change is timestamped with the actor.
   If the problem isn't actually fixed, the reporter can **reopen** within 14 days
   (max 3 reopens), sending it back to the admin for re-assignment.

## Priority scoring

`priority = category base + severity bonus (low 0 / medium 3 / high 6) + busy-area bonus (5)`
clamped to 0–20. High-severity issues in busy areas (Saddar, Gulshan-e-Iqbal,
Clifton, Shahrah-e-Faisal…) float to the top of every queue.

## State machine rules (enforced server-side)

- `submitted → verified | rejected` (admin only)
- `verified → in_progress | rejected` (admin only)
- `in_progress → resolved | rejected`
- `resolved → reopened` (reporter only, within window)
- `reopened → in_progress | rejected` (admin re-assigns)
- Illegal jumps return **HTTP 409** with a human-readable reason.
- Resolved/rejected are terminal for everyone except the reporter's reopen right.
