"""Complaint lifecycle state machine — the heart of Shikayat.

Pure functions, no I/O: fully unit-testable. Enforces the workflow:

    submitted → verified → in_progress → resolved
        ↘ rejected (admin)              ↖ reopened → in_progress (max 3 times)

Terminal states: resolved (unless reopened in window), rejected.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Final

# Ordered statuses for display
STATUSES: Final = (
    "submitted",
    "verified",
    "in_progress",
    "resolved",
    "rejected",
    "reopened",
)

# Who may perform each transition: (to_status, allowed_actor_roles)
TRANSITIONS: Final[dict[str, list[tuple[str, tuple[str, ...]]]]] = {
    "submitted": [
        ("verified", ("admin",)),
        ("rejected", ("admin",)),
    ],
    "verified": [
        ("in_progress", ("admin",)),  # admin assigns officer
        ("rejected", ("admin",)),
    ],
    "in_progress": [
        ("resolved", ("officer", "admin")),
        ("rejected", ("admin",)),
    ],
    "resolved": [
        ("reopened", ("citizen",)),  # only the reporter can reopen
    ],
    "reopened": [
        ("in_progress", ("admin",)),
        ("rejected", ("admin",)),
    ],
}

# Busy areas get an urgency bonus to the computed priority
BUSY_AREAS: Final[frozenset[str]] = frozenset(
    {
        "saddar",
        "gulshan-e-iqbal",
        "gulshan",
        "clifton",
        "johar",
        "i.i chundrigar",
        "shahrah-e-faisal",
        "faisal",
    }
)
SEVERITY_BONUS: Final[dict[str, int]] = {"low": 0, "medium": 3, "high": 6}


class IllegalTransitionError(ValueError):
    """Raised when a status change violates the state machine."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def can_transition(from_status: str, to_status: str, actor_role: str) -> bool:
    """Return True if actor_role may move a complaint from→to."""
    allowed = TRANSITIONS.get(from_status, [])
    return any(target == to_status and actor_role in roles for target, roles in allowed)


def assert_transition(from_status: str, to_status: str, actor_role: str) -> None:
    """Raise IllegalTransitionError with a human-readable reason if not allowed."""
    if from_status == to_status:
        raise IllegalTransitionError(f"Complaint is already '{from_status}'.")
    if from_status not in TRANSITIONS:
        raise IllegalTransitionError(f"'{from_status}' is a terminal state — no further changes allowed.")
    if not can_transition(from_status, to_status, actor_role):
        roles = ", ".join(sorted({r for _, rs in TRANSITIONS[from_status] for r in rs}))
        raise IllegalTransitionError(
            f"'{from_status}' → '{to_status}' is not allowed for role '{actor_role}'. Possible targets: {roles}."
        )


def compute_priority(base_priority: int, severity: str, area: str | None) -> int:
    """Deterministic priority score: category base + severity bonus + busy-area bonus.

    Clamped to [0, 20] so priorities stay comparable across categories.
    """
    area_key = (area or "").strip().lower()
    area_bonus = 5 if any(b in area_key for b in BUSY_AREAS) else 0
    raw = base_priority + SEVERITY_BONUS.get(severity, 0) + area_bonus
    return max(0, min(20, raw))


def can_reopen(
    complaint_status: str,
    resolved_at: datetime | None,
    reopen_count: int,
    now: datetime | None = None,
    window_days: int = 14,
    max_reopens: int = 3,
) -> bool:
    """A resolved complaint can be reopened by its reporter within the window, up to N times."""
    if complaint_status != "resolved":
        return False
    if reopen_count >= max_reopens:
        return False
    if resolved_at is None:
        return True
    now = now or datetime.now(UTC)
    resolved = resolved_at if resolved_at.tzinfo else resolved_at.replace(tzinfo=UTC)
    return now - resolved <= timedelta(days=window_days)


def next_ticket(sequence: int, year: int | None = None) -> str:
    """Build a human-friendly ticket number: SKT-2026-000042."""
    year = year or datetime.now(UTC).year
    return f"SKT-{year}-{sequence:06d}"
