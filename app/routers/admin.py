"""Admin router — officer management + stats overview."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_role
from ..models import Category, Complaint, User
from ..schemas import UserOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/officers", response_model=list[UserOut])
def list_officers(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return list(db.scalars(select(User).where(User.role == "officer").order_by(User.name)).all())


@router.get("/stats")
def stats(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Aggregate dashboard numbers for admins."""
    total = db.scalar(select(func.count(Complaint.id))) or 0
    open_count = (
        db.scalar(
            select(func.count(Complaint.id)).where(
                Complaint.status.in_(("submitted", "verified", "in_progress", "reopened"))
            )
        )
        or 0
    )
    resolved = db.scalar(select(func.count(Complaint.id)).where(Complaint.status == "resolved")) or 0
    rejected = db.scalar(select(func.count(Complaint.id)).where(Complaint.status == "rejected")) or 0
    citizens = db.scalar(select(func.count(User.id)).where(User.role == "citizen")) or 0
    officers = db.scalar(select(func.count(User.id)).where(User.role == "officer")) or 0

    by_status = {
        row.status: row.count
        for row in db.execute(select(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status)).all()
    }
    by_category = {
        row.slug: row.count
        for row in db.execute(
            select(Category.slug, func.count(Complaint.id))
            .join(Complaint, Complaint.category_id == Category.id)
            .group_by(Category.slug)
        ).all()
    }

    return {
        "total": total,
        "open": open_count,
        "resolved": resolved,
        "rejected": rejected,
        "citizens": citizens,
        "officers": officers,
        "by_status": by_status,
        "by_category": by_category,
        "resolve_rate": round(resolved / total * 100, 1) if total else 0.0,
    }
