"""Complaints router — create, list, transition lifecycle, comments."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..config import get_settings
from ..core.state_machine import (
    STATUSES,
    IllegalTransitionError,
    assert_transition,
    can_reopen,
    compute_priority,
    next_ticket,
)
from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..models import Category, Comment, Complaint, StatusHistory, User
from ..schemas import (
    AssignIn,
    CommentIn,
    CommentOut,
    ComplaintCreate,
    ComplaintOut,
    ComplaintUpdate,
    StatusChangeIn,
)

router = APIRouter(prefix="/api/complaints", tags=["complaints"])
settings = get_settings()

VALID_STATUSES = STATUSES


def _ticket_sequence(db: Session) -> int:
    """Next per-year ticket sequence: count of complaints created this year + 1."""
    year_start = datetime(datetime.now(UTC).year, 1, 1, tzinfo=UTC)
    count = db.scalar(select(func.count(Complaint.id)).where(Complaint.created_at >= year_start)) or 0
    return count + 1


def _get_or_404(db: Session, complaint_id: int) -> Complaint:
    complaint = db.scalar(
        select(Complaint)
        .options(
            joinedload(Complaint.category),
            joinedload(Complaint.reporter),
            joinedload(Complaint.assignee),
            joinedload(Complaint.history).joinedload(StatusHistory.actor),
            joinedload(Complaint.comments).joinedload(Comment.author),
        )
        .where(Complaint.id == complaint_id)
    )
    if complaint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
    return complaint


def _serialize(c: Complaint) -> ComplaintOut:
    return ComplaintOut(
        id=c.id,
        ticket=c.ticket,
        title=c.title,
        description=c.description,
        status=c.status,
        category_name=c.category.name if c.category else None,
        reporter_name=c.reporter.name if c.reporter else None,
        assignee_name=c.assignee.name if c.assignee else None,
        ward=c.ward,
        area=c.area,
        severity=c.severity,
        priority=c.priority,
        resolved_note=c.resolved_note,
        reject_reason=c.reject_reason,
        reopen_count=c.reopen_count,
        created_at=c.created_at,
        updated_at=c.updated_at,
        history=[
            {
                "id": h.id,
                "from_status": h.from_status,
                "to_status": h.to_status,
                "note": h.note,
                "actor_name": h.actor.name if h.actor else None,
                "created_at": h.created_at,
            }
            for h in c.history
        ],
        comments=[
            {
                "id": cm.id,
                "body": cm.body,
                "author_name": cm.author.name if cm.author else None,
                "created_at": cm.created_at,
            }
            for cm in c.comments
        ],
    )


def _ensure_can_view(complaint: Complaint, user: User) -> None:
    if user.role == "admin":
        return
    if user.role == "officer" and complaint.assignee_id == user.id:
        return
    if complaint.reporter_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")


@router.post("", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
def create_complaint(
    body: ComplaintCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Citizen (or any user) reports a new civic issue."""
    if user.role == "officer" and user.ward:
        body.ward = body.ward or user.ward  # noqa: PLW2901

    category = db.scalar(select(Category).where(Category.slug == body.category_slug))
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown category")

    complaint = Complaint(
        ticket=next_ticket(_ticket_sequence(db)),
        title=body.title.strip(),
        description=body.description.strip(),
        status="submitted",
        category_id=category.id,
        reporter_id=user.id,
        ward=body.ward.strip() if body.ward else None,
        area=body.area.strip() if body.area else None,
        severity=body.severity,
        priority=compute_priority(category.base_priority, body.severity, body.area),
    )
    db.add(complaint)
    db.flush()
    db.add(
        StatusHistory(
            complaint_id=complaint.id,
            from_status=None,
            to_status="submitted",
            actor_id=user.id,
            note="Complaint filed",
        )
    )
    db.commit()
    return _serialize(_get_or_404(db, complaint.id))


@router.get("", response_model=list[ComplaintOut])
def list_complaints(
    mine: bool = False,
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List complaints with role-aware scoping.

    - citizen: own complaints (or all if mine=false)
    - officer: complaints assigned to them
    - admin: everything
    """
    q = (
        select(Complaint)
        .options(
            joinedload(Complaint.category),
            joinedload(Complaint.reporter),
            joinedload(Complaint.assignee),
        )
        .order_by(Complaint.priority.desc(), Complaint.created_at.desc())
    )

    if user.role == "officer":
        q = q.where(Complaint.assignee_id == user.id)
    elif user.role == "citizen" and mine:
        q = q.where(Complaint.reporter_id == user.id)

    if status_filter:
        if status_filter not in VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Use one of: {', '.join(VALID_STATUSES)}",
            )
        q = q.where(Complaint.status == status_filter)
    if category:
        q = q.join(Category).where(Category.slug == category)

    return [_serialize(c) for c in db.scalars(q).all()]


@router.get("/{complaint_id}", response_model=ComplaintOut)
def get_complaint(
    complaint_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    complaint = _get_or_404(db, complaint_id)
    _ensure_can_view(complaint, user)
    return _serialize(complaint)


@router.patch("/{complaint_id}", response_model=ComplaintOut)
def update_complaint(
    complaint_id: int,
    body: ComplaintUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reporter may edit title/description while the complaint is still open."""
    complaint = _get_or_404(db, complaint_id)
    if complaint.reporter_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the reporter can edit this complaint")
    if complaint.status not in ("submitted", "verified", "in_progress"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Closed complaints cannot be edited")
    if body.title is not None:
        complaint.title = body.title.strip()
    if body.description is not None:
        complaint.description = body.description.strip()
    db.commit()
    return _serialize(_get_or_404(db, complaint_id))


@router.post("/{complaint_id}/transition", response_model=ComplaintOut)
def transition(
    complaint_id: int,
    body: StatusChangeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move a complaint through the lifecycle (verify/reject/assign/resolve/reopen)."""
    complaint = _get_or_404(db, complaint_id)

    # Special rule: reopen is only for the reporter of a resolved complaint
    try:
        if body.to_status == "reopened":
            if complaint.reporter_id != user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the reporter can reopen")
            if not can_reopen(
                complaint.status,
                complaint.resolved_at,
                complaint.reopen_count,
                window_days=settings.REOPEN_WINDOW_DAYS,
                max_reopens=settings.MAX_REOPENS,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Complaint can't be reopened (window {settings.REOPEN_WINDOW_DAYS} days, "
                    f"max {settings.MAX_REOPENS} reopens).",
                )
            assert_transition(complaint.status, body.to_status, "citizen")
        else:
            # Everyone else: enforce role rules from the state machine
            assert_transition(complaint.status, body.to_status, user.role)
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc

    # Admin-only guard for reject
    if body.to_status == "rejected" and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can reject complaints")

    # in_progress requires an assignee (set via /assign — enforce here too)
    if body.to_status == "in_progress" and complaint.assignee_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assign an officer before starting work")

    from_status = complaint.status
    complaint.status = body.to_status
    complaint.updated_at = datetime.now(UTC)

    if body.to_status == "resolved":
        complaint.resolved_note = body.note
        complaint.resolved_at = datetime.now(UTC)
    if body.to_status == "rejected":
        complaint.reject_reason = body.note
    if body.to_status == "reopened":
        complaint.reopen_count += 1

    db.add(
        StatusHistory(
            complaint_id=complaint.id,
            from_status=from_status,
            to_status=body.to_status,
            actor_id=user.id,
            note=body.note,
        )
    )
    db.commit()
    return _serialize(_get_or_404(db, complaint_id))


@router.post("/{complaint_id}/assign", response_model=ComplaintOut)
def assign(
    complaint_id: int,
    body: AssignIn,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Admin assigns a ward officer; complaint moves to in_progress."""
    complaint = _get_or_404(db, complaint_id)
    if complaint.status not in ("verified", "in_progress", "reopened"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only verified/reopened complaints can be assigned (current: {complaint.status})",
        )

    officer = db.get(User, body.officer_id)
    if officer is None or officer.role != "officer":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected user is not an officer")

    if complaint.status != "in_progress":
        from_status = complaint.status
        complaint.status = "in_progress"
        db.add(
            StatusHistory(
                complaint_id=complaint.id,
                from_status=from_status,
                to_status="in_progress",
                actor_id=user.id,
                note=f"Assigned to {officer.name}",
            )
        )
    complaint.assignee_id = officer.id
    if body.ward:
        complaint.ward = body.ward.strip()
    complaint.updated_at = datetime.now(UTC)
    db.commit()
    return _serialize(_get_or_404(db, complaint_id))


@router.post("/{complaint_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    complaint_id: int,
    body: CommentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    complaint = _get_or_404(db, complaint_id)
    _ensure_can_view(complaint, user)
    comment = Comment(complaint_id=complaint.id, author_id=user.id, body=body.body.strip())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return CommentOut(
        id=comment.id,
        body=comment.body,
        author_name=user.name,
        created_at=comment.created_at,
    )
