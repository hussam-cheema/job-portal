from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.database import get_db
from app.models import User
from app.schemas import InfrastructureDashboard
from app.services.infrastructure import infrastructure_dashboard

router = APIRouter()


@router.get("/admin/infrastructure", response_model=InfrastructureDashboard)
def admin_infrastructure_dashboard(
    refresh: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return infrastructure_dashboard(db, force_refresh=refresh)
