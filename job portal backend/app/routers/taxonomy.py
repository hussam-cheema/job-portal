from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.database import get_db
from app.models import Job, TaxonomyTerm, User
from app.schemas import TaxonomyTermIn, TaxonomyTermOut, TaxonomyTermUpdate
from app.services.taxonomy import ensure_default_taxonomy
from app.utils import as_list, slugify

router = APIRouter()


def _rows(db: Session, *, active_only: bool) -> list[TaxonomyTerm]:
    ensure_default_taxonomy(db)
    stmt = select(TaxonomyTerm).where(TaxonomyTerm.kind == "category")
    if active_only:
        stmt = stmt.where(TaxonomyTerm.is_active.is_(True))
    return db.execute(stmt.order_by(TaxonomyTerm.name.asc())).scalars().all()


@router.get("/taxonomy", response_model=list[TaxonomyTermOut])
def public_taxonomy(db: Session = Depends(get_db)):
    rows = _rows(db, active_only=True)
    db.commit()
    return rows


@router.get("/admin/taxonomy", response_model=list[TaxonomyTermOut])
def admin_taxonomy(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    rows = _rows(db, active_only=False)
    db.commit()
    return rows


@router.post("/admin/taxonomy", response_model=TaxonomyTermOut)
def create_term(
    payload: TaxonomyTermIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    name = payload.name.strip()
    slug = slugify(payload.slug or name)
    if not slug:
        raise HTTPException(status_code=400, detail="A valid name or slug is required")
    duplicate = db.execute(
        select(TaxonomyTerm).where(
            TaxonomyTerm.kind == payload.kind,
            or_(
                TaxonomyTerm.slug == slug,
                func.lower(TaxonomyTerm.name) == name.lower(),
            ),
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=400, detail="This slug already exists")
    row = TaxonomyTerm(
        id=str(uuid4()),
        name=name,
        slug=slug,
        kind=payload.kind,
        is_active=payload.is_active,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/admin/taxonomy/{term_id}", response_model=TaxonomyTermOut)
def update_term(
    term_id: str,
    payload: TaxonomyTermUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    row = db.get(TaxonomyTerm, term_id)
    if not row:
        raise HTTPException(status_code=404, detail="Tag/category not found")
    old_name = row.name
    data = payload.model_dump(exclude_unset=True)
    if data.get("name") is not None:
        candidate_name = data["name"].strip()
        duplicate_name = db.execute(
            select(TaxonomyTerm).where(
                TaxonomyTerm.kind == row.kind,
                func.lower(TaxonomyTerm.name) == candidate_name.lower(),
                TaxonomyTerm.id != row.id,
            )
        ).scalar_one_or_none()
        if duplicate_name:
            raise HTTPException(status_code=400, detail="This name already exists")
        row.name = candidate_name
    if data.get("slug") is not None:
        candidate = slugify(data["slug"])
        duplicate = db.execute(
            select(TaxonomyTerm).where(
                TaxonomyTerm.kind == row.kind,
                TaxonomyTerm.slug == candidate,
                TaxonomyTerm.id != row.id,
            )
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=400, detail="This slug already exists")
        row.slug = candidate
    if data.get("is_active") is not None:
        row.is_active = data["is_active"]
    if row.name.casefold() != old_name.casefold():
        for job in db.execute(select(Job)).scalars().all():
            values = as_list(job.tags)
            if any(value.casefold() == old_name.casefold() for value in values):
                job.tags = [
                    row.name if value.casefold() == old_name.casefold() else value
                    for value in values
                ]
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


@router.delete("/admin/taxonomy/{term_id}")
def delete_term(
    term_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    row = db.get(TaxonomyTerm, term_id)
    if not row:
        raise HTTPException(status_code=404, detail="Tag/category not found")
    in_use = any(
        row.name.lower() in {value.lower() for value in as_list(job.tags)}
        for job in db.execute(select(Job)).scalars().all()
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="This tag/category is used by one or more jobs. Deactivate it instead.",
        )
    db.delete(row)
    db.commit()
    return {"ok": True, "id": term_id}
