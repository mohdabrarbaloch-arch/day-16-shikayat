"""Officer router — ward officers' queue operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..dependencies import require_role
from ..models import Complaint, User
from ..schemas import ComplaintOut

router = APIRouter(prefix="/api/officers", tags=["officers"])


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
    )


@router.get("/me/queue", response_model=list[ComplaintOut])
def my_queue(user: User = Depends(require_role("officer")), db: Session = Depends(get_db)):
    """Complaints assigned to the current officer, open ones first."""
    q = (
        select(Complaint)
        .options(joinedload(Complaint.category), joinedload(Complaint.reporter))
        .where(Complaint.assignee_id == user.id)
        .order_by(Complaint.status.in_(("in_progress", "reopened")).desc(), Complaint.priority.desc())
    )
    return [_serialize(c) for c in db.scalars(q).all()]


@router.get("/{officer_id}/complaints", response_model=list[ComplaintOut])
def officer_complaints(
    officer_id: int,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    officer = db.get(User, officer_id)
    if officer is None or officer.role != "officer":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Officer not found")
    q = (
        select(Complaint)
        .options(joinedload(Complaint.category), joinedload(Complaint.reporter))
        .where(Complaint.assignee_id == officer_id)
        .order_by(Complaint.created_at.desc())
    )
    return [_serialize(c) for c in db.scalars(q).all()]
