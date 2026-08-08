from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.config import canonical_site_url, site_url
from app.database import get_db
from app.logging_config import get_logger
from app.models import SEOMeta, User
from app.schemas import (
    BacklinkIn,
    SEODashboard,
    SEOMetaOut,
    SocialSettingsIn,
    YoastAnalyzeIn,
)
from app.services.seo import build_seo_dashboard, get_seo_for_entity
from app.services.seo_tools import (
    add_backlink,
    authority_score,
    build_sitemap_urls,
    discover_backlinks_basic,
    entity_rank_summary,
    gsc_credentials_configured,
    get_setting,
    get_social_settings,
    list_backlinks,
    list_keyword_ranks,
    measure_pagespeed,
    robots_txt,
    set_social_settings,
    sync_gsc_data,
)
from app.services.yoast import analyze_yoast

router = APIRouter()
logger = get_logger("jobportal.seo_router")


@router.get("/admin/seo/dashboard", response_model=SEODashboard)
def seo_dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    try:
        data = build_seo_dashboard(db)
        base = canonical_site_url()
        pagespeed = measure_pagespeed(base)
        gsc_status = {
            "connected": bool(get_setting(db, "gsc_last_sync") or os.getenv("GSC_SITE_URL")),
            "last_sync": get_setting(db, "gsc_last_sync"),
            "period_start": get_setting(db, "gsc_period_start"),
            "period_end": get_setting(db, "gsc_period_end"),
            "site_url": os.getenv("GSC_SITE_URL") or get_setting(db, "gsc_site_url"),
            "data_source": "Google Search Console Search Analytics API",
            "position_note": (
                "Average position is the topmost position recorded across actual impressions; "
                "it is not a live or fixed result for every search."
            ),
            "message": (
                "GSC ready — use Sync Search Console."
                if gsc_credentials_configured()
                else "Set GSC_SITE_URL + GSC_SERVICE_ACCOUNT_JSON to connect Search Console."
            ),
        }
        data.update(
            {
                "gsc": gsc_status,
                "pagespeed": pagespeed,
                "authority": authority_score(db),
                "backlinks": list_backlinks(db),
                "keyword_ranks": list_keyword_ranks(db, 50),
                "url_ranks": entity_rank_summary(db),
                "social": get_social_settings(db),
                "sitemap_url": f"{base}/sitemap.xml",
                "robots_url": f"{base}/robots.txt",
                "robots_preview": robots_txt(),
            }
        )
        # fold pagespeed into performance panel
        perf = dict(data.get("performance") or {})
        perf["load_score_pct"] = pagespeed.get("score", 0)
        perf["pagespeed"] = pagespeed
        data["performance"] = perf
        return SEODashboard(**data)
    except Exception:
        logger.exception("seo_dashboard failed")
        raise HTTPException(status_code=500, detail="Failed to load SEO dashboard") from None


@router.post("/admin/seo/gsc/sync")
def gsc_sync(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    try:
        return sync_gsc_data(db)
    except Exception:
        logger.exception("gsc_sync failed")
        raise HTTPException(status_code=500, detail="GSC sync failed") from None


@router.post("/admin/seo/pagespeed")
def run_pagespeed(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    try:
        result = measure_pagespeed(site_url())
        return result
    except Exception:
        logger.exception("pagespeed failed")
        raise HTTPException(status_code=500, detail="PageSpeed failed") from None


@router.get("/admin/seo/social")
def get_social(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    return get_social_settings(db)


@router.put("/admin/seo/social")
def put_social(
    payload: SocialSettingsIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return set_social_settings(db, payload.model_dump(exclude_unset=True))


@router.get("/settings/social")
def public_social(db: Session = Depends(get_db)):
    """Public social URLs for footer icons."""
    try:
        return get_social_settings(db)
    except Exception:
        return {
            "facebook_url": "",
            "youtube_url": "",
            "x_url": "",
            "linkedin_url": "",
        }


@router.get("/admin/seo/backlinks")
def admin_backlinks(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    return list_backlinks(db)


@router.post("/admin/seo/backlinks")
def create_backlink(
    payload: BacklinkIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        return add_backlink(
            db,
            source_url=payload.source_url,
            target_url=payload.target_url,
            anchor_text=payload.anchor_text,
            notes=payload.notes,
            is_dofollow=payload.is_dofollow,
        )
    except Exception:
        logger.exception("create_backlink failed")
        raise HTTPException(status_code=500, detail="Failed to add backlink") from None


@router.post("/admin/seo/backlinks/discover")
def discover_backlinks(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    return discover_backlinks_basic(db)


@router.post("/admin/seo/yoast/analyze")
def yoast_analyze(payload: YoastAnalyzeIn, _: User = Depends(get_current_admin)):
    try:
        return analyze_yoast(
            title=payload.title,
            content_html=payload.content,
            meta_title=payload.meta_title,
            meta_description=payload.meta_description,
            focus_keyword=payload.focus_keyword,
            slug=payload.slug,
        )
    except Exception:
        logger.exception("yoast_analyze failed")
        raise HTTPException(status_code=500, detail="Analysis failed") from None


@router.get("/seo/{entity_type}/{entity_id}", response_model=SEOMetaOut | None)
def public_seo(entity_type: str, entity_id: str, db: Session = Depends(get_db)):
    try:
        row = get_seo_for_entity(db, entity_type, entity_id)
        if not row:
            return None
        return SEOMetaOut.model_validate(row)
    except Exception:
        logger.exception("public_seo failed")
        return None


@router.get("/admin/seo", response_model=list[SEOMetaOut])
def list_seo(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    try:
        rows = db.execute(select(SEOMeta).order_by(SEOMeta.updated_at.desc())).scalars().all()
        return [SEOMetaOut.model_validate(r) for r in rows]
    except Exception:
        logger.exception("list_seo failed")
        return []


@router.get("/sitemap-data")
def sitemap_data(db: Session = Depends(get_db)):
    """JSON list of sitemap URLs (used by frontend sitemap.xml)."""
    try:
        return {"urls": build_sitemap_urls(db)}
    except Exception:
        logger.exception("sitemap_data failed")
        return {"urls": []}
