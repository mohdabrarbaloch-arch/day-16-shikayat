"""Public stats endpoint for citizens — no auth needed."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Complaint

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/public")
def public_stats(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(Complaint.id))) or 0
    resolved = db.scalar(select(func.count(Complaint.id)).where(Complaint.status == "resolved")) or 0
    by_category = {
        row.slug: row.count
        for row in db.execute(
            select(Category.slug, func.count(Complaint.id))
            .join(Complaint, Complaint.category_id == Category.id)
            .group_by(Category.slug)
        ).all()
    }
    return {
        "total_reported": total,
        "resolved": resolved,
        "by_category": by_category,
    }
