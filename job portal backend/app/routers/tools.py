from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.config import jwt_secret
from app.database import get_db
from app.logging_config import get_logger
from app.models import SiteSetting, ToolCategory, ToolPage, ToolUsageEvent, User
from app.routers.analytics import ANALYTICS_TIMEZONE_NAME, BOT_PATTERN, _client_ip, _month_bounds, _utc_aware
from app.schemas import (
    ToolAnalyticsOut,
    ToolAnalyticsRow,
    ToolAdminResponse,
    ToolCategoryIn,
    ToolCategoryOut,
    ToolCategoryUpdate,
    ToolPageIn,
    ToolPageOut,
    ToolPageUpdate,
    ToolUsageIn,
    ToolUsageOut,
)
from app.services.seo import delete_seo, upsert_tool_seo
from app.utils import slugify

router = APIRouter()
logger = get_logger("jobportal.tools")

_COLOR_CURSOR_KEY = "tool_category_color_cursor"
_DEFAULT_ICONS = ("coins", "graduation", "image", "document", "calculator", "sparkles")


def _serialize_category(category: ToolCategory, tools: list[ToolPage]) -> ToolCategoryOut:
    return ToolCategoryOut(
        id=category.id,
        slug=category.slug,
        title=category.title,
        content=category.content,
        icon_key=category.icon_key,
        color_index=category.color_index,
        sort_order=category.sort_order,
        is_published=category.is_published,
        tools=[ToolPageOut.model_validate(tool) for tool in tools],
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def _load_categories(db: Session, *, public_only: bool) -> list[ToolCategoryOut]:
    category_query = select(ToolCategory)
    tool_query = select(ToolPage)
    if public_only:
        category_query = category_query.where(ToolCategory.is_published.is_(True))
        tool_query = tool_query.where(ToolPage.is_published.is_(True))
    categories = db.execute(
        category_query.order_by(ToolCategory.sort_order.asc(), ToolCategory.title.asc())
    ).scalars().all()
    if not categories:
        return []
    category_ids = [category.id for category in categories]
    tools = db.execute(
        tool_query.where(ToolPage.category_id.in_(category_ids)).order_by(
            ToolPage.sort_order.asc(), ToolPage.title.asc()
        )
    ).scalars().all()
    by_category: dict[str, list[ToolPage]] = {category_id: [] for category_id in category_ids}
    for tool in tools:
        by_category.setdefault(tool.category_id, []).append(tool)
    return [_serialize_category(category, by_category.get(category.id, [])) for category in categories]


def _next_color_index(db: Session) -> int:
    maximum = db.execute(select(func.max(ToolCategory.color_index))).scalar() or 0
    cursor = db.get(SiteSetting, _COLOR_CURSOR_KEY)
    try:
        previous = int(cursor.value or 0) if cursor else 0
    except (TypeError, ValueError):
        previous = 0
    value = max(maximum, previous) + 1
    if cursor:
        cursor.value = str(value)
        cursor.updated_at = datetime.utcnow()
    else:
        db.add(SiteSetting(key=_COLOR_CURSOR_KEY, value=str(value), updated_at=datetime.utcnow()))
    return value


@router.get("/tools", response_model=list[ToolCategoryOut])
def public_tools(db: Session = Depends(get_db)):
    return _load_categories(db, public_only=True)


@router.get("/tools/categories/{slug}", response_model=ToolCategoryOut)
def public_tool_category(slug: str, db: Session = Depends(get_db)):
    category = db.execute(
        select(ToolCategory).where(
            ToolCategory.slug == slug,
            ToolCategory.is_published.is_(True),
        )
    ).scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Tool category not found")
    tools = db.execute(
        select(ToolPage).where(
            ToolPage.category_id == category.id,
            ToolPage.is_published.is_(True),
        ).order_by(ToolPage.sort_order.asc(), ToolPage.title.asc())
    ).scalars().all()
    return _serialize_category(category, tools)


@router.get("/tools/{slug}", response_model=ToolPageOut)
def public_tool(slug: str, db: Session = Depends(get_db)):
    tool = db.execute(
        select(ToolPage).where(
            ToolPage.slug == slug,
            ToolPage.is_published.is_(True),
        )
    ).scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.post("/tools/{slug}/usage", response_model=ToolUsageOut, status_code=201)
def record_tool_usage(
    slug: str,
    payload: ToolUsageIn,
    request: Request,
    db: Session = Depends(get_db),
):
    tool = db.execute(
        select(ToolPage).where(ToolPage.slug == slug, ToolPage.is_published.is_(True))
    ).scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if BOT_PATTERN.search(request.headers.get("user-agent") or ""):
        return ToolUsageOut(counted=False)

    secret = jwt_secret().encode()
    visitor_hash = hmac.new(secret, payload.visitor_id.encode(), hashlib.sha256).hexdigest()
    ip = _client_ip(request)
    client_hash = hmac.new(secret, ip.encode(), hashlib.sha256).hexdigest() if ip else None
    now = datetime.utcnow()
    previous = db.execute(
        select(ToolUsageEvent.id).where(
            ToolUsageEvent.tool_id == tool.id,
            ToolUsageEvent.visitor_hash == visitor_hash,
            ToolUsageEvent.event_type == payload.event_type,
            ToolUsageEvent.occurred_at >= now - timedelta(minutes=30),
        ).limit(1)
    ).scalar_one_or_none()
    if previous:
        return ToolUsageOut(counted=False)
    # A hashed-IP ceiling limits artificial floods without storing an address.
    # The browser/tool dedupe above prevents normal repeated input events from
    # consuming this allowance.
    if client_hash:
        recent_client_events = db.execute(
            select(func.count(ToolUsageEvent.id)).where(
                ToolUsageEvent.client_hash == client_hash,
                ToolUsageEvent.occurred_at >= now - timedelta(hours=1),
            )
        ).scalar_one()
        if recent_client_events >= 300:
            raise HTTPException(status_code=429, detail="Tool analytics rate limit reached")

    window_start = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0)
    db.add(ToolUsageEvent(
        id=str(uuid4()), tool_id=tool.id, visitor_hash=visitor_hash,
        client_hash=client_hash, event_type=payload.event_type,
        window_start=window_start, occurred_at=now,
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return ToolUsageOut(counted=False)
    return ToolUsageOut(counted=True)


@router.get("/admin/tools", response_model=ToolAdminResponse)
def admin_tools(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    categories = _load_categories(db, public_only=False)
    tools = [tool for category in categories for tool in category.tools]
    return ToolAdminResponse(categories=categories, tools=tools)


@router.get("/admin/tools/analytics", response_model=ToolAnalyticsOut)
def admin_tool_analytics(
    month: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    label, start, end = _month_bounds(month)
    rows = db.execute(
        select(ToolPage, ToolCategory.title)
        .join(ToolCategory, ToolPage.category_id == ToolCategory.id)
        .order_by(ToolCategory.sort_order, ToolCategory.title, ToolPage.sort_order, ToolPage.title)
    ).all()
    counts = db.execute(
        select(ToolUsageEvent.tool_id, ToolUsageEvent.event_type, func.count(ToolUsageEvent.id))
        .where(ToolUsageEvent.occurred_at >= start, ToolUsageEvent.occurred_at < end)
        .group_by(ToolUsageEvent.tool_id, ToolUsageEvent.event_type)
    ).all()
    by_tool = {(tool_id, event_type): count for tool_id, event_type, count in counts}
    tools = [
        ToolAnalyticsRow(
            id=tool.id,
            category_id=tool.category_id,
            category_title=category_title,
            slug=tool.slug,
            title=tool.title,
            tool_kind=tool.tool_kind,
            is_published=tool.is_published,
            opens=by_tool.get((tool.id, "open"), 0),
            uses=by_tool.get((tool.id, "interaction"), 0),
        )
        for tool, category_title in rows
    ]
    return ToolAnalyticsOut(
        month=label,
        timezone=ANALYTICS_TIMEZONE_NAME,
        total_opens=sum(tool.opens for tool in tools),
        total_uses=sum(tool.uses for tool in tools),
        tools=tools,
        generated_at=_utc_aware(datetime.utcnow()),
    )


@router.post("/admin/tool-categories", response_model=ToolCategoryOut)
def create_tool_category(
    payload: ToolCategoryIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    slug = slugify(payload.slug or payload.title)
    if db.execute(select(ToolCategory.id).where(ToolCategory.slug == slug)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Category slug already exists")
    color_index = _next_color_index(db)
    category = ToolCategory(
        id=str(uuid4()),
        slug=slug,
        title=payload.title.strip(),
        content=payload.content or "",
        icon_key=(payload.icon_key or _DEFAULT_ICONS[(color_index - 1) % len(_DEFAULT_ICONS)]).strip(),
        color_index=color_index,
        sort_order=payload.sort_order,
        is_published=payload.is_published,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(category)
    upsert_tool_seo(
        db,
        category,
        entity_type="tool_category",
        path=f"/tools/categories/{category.slug}",
        seo_override=payload.seo.model_dump() if payload.seo else None,
    )
    db.commit()
    db.refresh(category)
    return _serialize_category(category, [])


@router.put("/admin/tool-categories/{category_id}", response_model=ToolCategoryOut)
def update_tool_category(
    category_id: str,
    payload: ToolCategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    category = db.get(ToolCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Tool category not found")
    data = payload.model_dump(exclude_unset=True)
    seo = data.pop("seo", None)
    if "slug" in data:
        candidate = slugify(data.pop("slug") or category.title)
        duplicate = db.execute(
            select(ToolCategory.id).where(ToolCategory.slug == candidate, ToolCategory.id != category_id)
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=400, detail="Category slug already exists")
        category.slug = candidate
    for key in ("title", "content", "icon_key", "sort_order", "is_published"):
        if key in data and data[key] is not None:
            setattr(category, key, data[key].strip() if key in {"title", "icon_key"} else data[key])
    category.updated_at = datetime.utcnow()
    upsert_tool_seo(
        db,
        category,
        entity_type="tool_category",
        path=f"/tools/categories/{category.slug}",
        seo_override=seo if isinstance(seo, dict) else None,
    )
    tools = db.execute(
        select(ToolPage).where(ToolPage.category_id == category.id).order_by(
            ToolPage.sort_order.asc(), ToolPage.title.asc()
        )
    ).scalars().all()
    db.commit()
    return _serialize_category(category, tools)


@router.delete("/admin/tool-categories/{category_id}")
def delete_tool_category(
    category_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    category = db.get(ToolCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Tool category not found")
    tool_count = db.execute(
        select(func.count()).select_from(ToolPage).where(ToolPage.category_id == category_id)
    ).scalar() or 0
    if tool_count:
        raise HTTPException(status_code=409, detail="Delete or move this category's tools first")
    delete_seo(db, "tool_category", category_id)
    db.delete(category)
    db.commit()
    return {"ok": True, "id": category_id}


@router.post("/admin/tool-pages", response_model=ToolPageOut)
def create_tool_page(
    payload: ToolPageIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    if not db.get(ToolCategory, payload.category_id):
        raise HTTPException(status_code=400, detail="Tool category does not exist")
    slug = slugify(payload.slug or payload.title)
    if db.execute(select(ToolPage.id).where(ToolPage.slug == slug)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Tool slug already exists")
    tool = ToolPage(
        id=str(uuid4()),
        category_id=payload.category_id,
        slug=slug,
        title=payload.title.strip(),
        content=payload.content or "",
        tool_kind=payload.tool_kind,
        sort_order=payload.sort_order,
        is_published=payload.is_published,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(tool)
    upsert_tool_seo(
        db,
        tool,
        entity_type="tool",
        path=f"/tools/{tool.slug}",
        seo_override=payload.seo.model_dump() if payload.seo else None,
    )
    db.commit()
    db.refresh(tool)
    return tool


@router.put("/admin/tool-pages/{tool_id}", response_model=ToolPageOut)
def update_tool_page(
    tool_id: str,
    payload: ToolPageUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    tool = db.get(ToolPage, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    data = payload.model_dump(exclude_unset=True)
    seo = data.pop("seo", None)
    if "category_id" in data:
        category_id = data.pop("category_id")
        if not category_id or not db.get(ToolCategory, category_id):
            raise HTTPException(status_code=400, detail="Tool category does not exist")
        tool.category_id = category_id
    if "slug" in data:
        candidate = slugify(data.pop("slug") or tool.title)
        duplicate = db.execute(
            select(ToolPage.id).where(ToolPage.slug == candidate, ToolPage.id != tool_id)
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=400, detail="Tool slug already exists")
        tool.slug = candidate
    for key in ("title", "content", "tool_kind", "sort_order", "is_published"):
        if key in data and data[key] is not None:
            setattr(tool, key, data[key].strip() if key == "title" else data[key])
    tool.updated_at = datetime.utcnow()
    upsert_tool_seo(
        db,
        tool,
        entity_type="tool",
        path=f"/tools/{tool.slug}",
        seo_override=seo if isinstance(seo, dict) else None,
    )
    db.commit()
    db.refresh(tool)
    return tool


@router.delete("/admin/tool-pages/{tool_id}")
def delete_tool_page(
    tool_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    tool = db.get(ToolPage, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    delete_seo(db, "tool", tool_id)
    db.delete(tool)
    db.commit()
    return {"ok": True, "id": tool_id}
