"""Tests for the complaint lifecycle state machine (pure logic, no I/O)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.state_machine import (
    IllegalTransitionError,
    assert_transition,
    can_reopen,
    can_transition,
    compute_priority,
    next_ticket,
)


class TestTransitions:
    def test_submitted_can_be_verified_by_admin(self):
        assert can_transition("submitted", "verified", "admin") is True

    def test_submitted_cannot_be_verified_by_citizen(self):
        assert can_transition("submitted", "verified", "citizen") is False

    def test_citizen_cannot_reject(self):
        assert can_transition("submitted", "rejected", "citizen") is False
        assert can_transition("in_progress", "rejected", "officer") is False

    def test_officer_can_resolve_assigned_work(self):
        assert can_transition("in_progress", "resolved", "officer") is True

    def test_reporter_can_reopen_resolved(self):
        assert can_transition("resolved", "reopened", "citizen") is True

    def test_resolved_is_terminal_for_admin(self):
        # Admin cannot move a resolved complaint anywhere
        assert can_transition("resolved", "in_progress", "admin") is False

    def test_reopened_goes_back_to_in_progress(self):
        assert can_transition("reopened", "in_progress", "admin") is True

    def test_illegal_jump_raises(self):
        with pytest.raises(IllegalTransitionError):
            assert_transition("submitted", "resolved", "citizen")

    def test_same_status_raises(self):
        with pytest.raises(IllegalTransitionError):
            assert_transition("submitted", "submitted", "admin")

    def test_terminal_state_message(self):
        with pytest.raises(IllegalTransitionError, match="terminal"):
            assert_transition("rejected", "submitted", "admin")

    def test_error_message_lists_roles(self):
        with pytest.raises(IllegalTransitionError, match="admin"):
            assert_transition("submitted", "verified", "officer")


class TestPriority:
    def test_base_only(self):
        assert compute_priority(5, "low", None) == 5

    def test_severity_bonus(self):
        assert compute_priority(5, "high", None) == 11
        assert compute_priority(5, "medium", None) == 8

    def test_busy_area_bonus(self):
        assert compute_priority(4, "low", "Saddar") == 9

    def test_busy_area_partial_match(self):
        assert compute_priority(0, "low", "Gulshan Block 7") == 5

    def test_normal_area_no_bonus(self):
        assert compute_priority(4, "low", "North Nazimabad") == 4

    def test_clamped_at_20(self):
        assert compute_priority(20, "high", "Saddar") == 20

    def test_case_insensitive_area(self):
        assert compute_priority(0, "low", "SADDAR") == 5


class TestReopen:
    def test_resolved_within_window(self):
        resolved = datetime.now(UTC) - timedelta(days=2)
        assert can_reopen("resolved", resolved, 0) is True

    def test_expired_window(self):
        resolved = datetime.now(UTC) - timedelta(days=30)
        assert can_reopen("resolved", resolved, 0) is False

    def test_max_reopens(self):
        resolved = datetime.now(UTC) - timedelta(days=1)
        assert can_reopen("resolved", resolved, 3) is False

    def test_only_resolved_can_reopen(self):
        assert can_reopen("in_progress", None, 0) is False


class TestTicket:
    def test_ticket_format(self):
        assert next_ticket(1, 2026) == "SKT-2026-000001"

    def test_ticket_padding(self):
        assert next_ticket(123, 2026) == "SKT-2026-000123"

    def test_ticket_default_year(self):
        ticket = next_ticket(42)
        assert ticket.startswith("SKT-")
        assert ticket.endswith("-000042")
