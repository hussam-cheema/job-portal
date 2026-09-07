from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MarketReport
from app.services.market_reports import month_date, report_summary

router = APIRouter(prefix="/market-reports", tags=["Public market reports"])


@router.get("")
def list_reports(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=300"
    reports = db.scalars(select(MarketReport).order_by(MarketReport.month.desc())).all()
    return {"reports": [report_summary(report.data) for report in reports]}


@router.get("/{month}")
def get_report(month: str, response: Response, db: Session = Depends(get_db)):
    try:
        month_date(month)
    except ValueError:
        raise HTTPException(status_code=404, detail="Monthly report not found")
    report = db.get(MarketReport, month)
    if report is None:
        raise HTTPException(status_code=404, detail="Monthly report not found")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return report.data
