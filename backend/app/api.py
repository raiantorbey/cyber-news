from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import desc, func, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Article, ArticleCVELink, IngestionRun, RunStatus, Source, Tool, Vulnerability
from app.schemas import (
    ArticleDetail, ArticleSummary, HealthResponse, OverviewResponse, Page, SourceResponse,
    ToolResponse, VulnerabilityDetail, VulnerabilitySummary,
)

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]
PageNumber = Annotated[int, Query(ge=1, le=10_000)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def _page(session: Session, statement, page: int, page_size: int):
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    items = list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).unique())
    return items, total


def _contains(column, value: str):
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return column.ilike(f"%{escaped}%", escape="\\")


@router.get("/health", response_model=HealthResponse)
def health(response: Response, db: DB, settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        latest = db.scalar(
            select(func.max(IngestionRun.finished_at)).where(IngestionRun.status == RunStatus.SUCCEEDED)
        )
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="unhealthy", database="unavailable", ingestion="unknown", last_ingestion_at=None)
    if latest is None:
        ingestion = "never"
    else:
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        ingestion = "fresh" if datetime.now(timezone.utc) - latest <= timedelta(seconds=settings.freshness_threshold_seconds) else "stale"
    return HealthResponse(
        status="ok" if ingestion == "fresh" else "degraded",
        database="ok",
        ingestion=ingestion,
        last_ingestion_at=latest,
    )


@router.get("/api/v1/overview", response_model=OverviewResponse)
def overview(db: DB) -> OverviewResponse:
    now = datetime.now(timezone.utc)
    article_count = db.scalar(select(func.count(Article.id)).where(Article.published_at >= now - timedelta(days=1))) or 0
    vulnerability_count = db.scalar(select(func.count(Vulnerability.cve_id)).where(Vulnerability.published_at >= now - timedelta(days=7))) or 0
    kev_count = db.scalar(select(func.count(Vulnerability.cve_id)).where(Vulnerability.kev.is_(True))) or 0
    tool_count = db.scalar(select(func.count(Tool.id)).where(Tool.discovered_at >= now - timedelta(days=7))) or 0
    article_stmt = select(Article).options(
        selectinload(Article.source), selectinload(Article.vulnerabilities)
    ).order_by(Article.published_at.desc()).limit(8)
    urgent_stmt = select(Vulnerability).where(Vulnerability.kev.is_(True)).order_by(Vulnerability.date_added.desc()).limit(8)
    tool_stmt = select(Tool).order_by(Tool.discovered_at.desc()).limit(8)
    return OverviewResponse(
        article_count_24h=article_count,
        vulnerability_count_7d=vulnerability_count,
        kev_count=kev_count,
        tool_count_7d=tool_count,
        latest_articles=list(db.scalars(article_stmt)),
        urgent_vulnerabilities=list(db.scalars(urgent_stmt)),
        latest_tools=list(db.scalars(tool_stmt)),
    )


@router.get("/api/v1/articles", response_model=Page[ArticleSummary])
def articles(
    db: DB,
    page: PageNumber = 1,
    page_size: PageSize = 25,
    category: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    source_id: Annotated[int | None, Query(ge=1)] = None,
    cve_id: Annotated[str | None, Query(pattern=r"(?i)^CVE-\d{4}-\d{4,7}$")] = None,
    q: Annotated[str | None, Query(min_length=2, max_length=200)] = None,
    published_after: datetime | None = None,
    published_before: datetime | None = None,
) -> Page[ArticleSummary]:
    if published_after and published_before and published_after > published_before:
        raise HTTPException(422, "published_after must not be later than published_before")
    statement = select(Article).options(
        selectinload(Article.source), selectinload(Article.vulnerabilities)
    )
    if cve_id:
        statement = statement.join(ArticleCVELink).where(ArticleCVELink.cve_id == cve_id.upper())
    filters = []
    if category:
        filters.append(Article.category == category.lower())
    if source_id:
        filters.append(Article.source_id == source_id)
    if q:
        filters.append(or_(_contains(Article.title, q), _contains(Article.excerpt, q)))
    if published_after:
        filters.append(Article.published_at >= published_after)
    if published_before:
        filters.append(Article.published_at <= published_before)
    items, total = _page(db, statement.where(*filters).order_by(Article.published_at.desc()), page, page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/api/v1/articles/{article_id}", response_model=ArticleDetail)
def article_detail(article_id: int, db: DB) -> Article:
    article = db.scalar(
        select(Article).where(Article.id == article_id).options(
            selectinload(Article.source), selectinload(Article.vulnerabilities)
        )
    )
    if article is None:
        raise HTTPException(404, "Article not found")
    return article


@router.get("/api/v1/articles/{article_id}/image")
def article_image(article_id: int, db: DB) -> Response:
    article = db.get(Article, article_id)
    if article is None or not article.image_bytes:
        raise HTTPException(404, "Image not found")
    return Response(
        content=article.image_bytes,
        media_type=article.image_content_type or "image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/api/v1/vulnerabilities", response_model=Page[VulnerabilitySummary])
def vulnerabilities(
    db: DB,
    page: PageNumber = 1,
    page_size: PageSize = 25,
    severity: Annotated[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None, Query()] = None,
    kev: bool | None = None,
    min_cvss: Annotated[float | None, Query(ge=0, le=10)] = None,
    vendor: Annotated[str | None, Query(min_length=1, max_length=300)] = None,
    q: Annotated[str | None, Query(min_length=2, max_length=200)] = None,
) -> Page[VulnerabilitySummary]:
    filters = []
    if severity:
        filters.append(Vulnerability.severity == severity)
    if kev is not None:
        filters.append(Vulnerability.kev.is_(kev))
    if min_cvss is not None:
        filters.append(Vulnerability.cvss_score >= min_cvss)
    if vendor:
        filters.append(_contains(Vulnerability.vendor, vendor))
    if q:
        filters.append(or_(_contains(Vulnerability.cve_id, q), _contains(Vulnerability.description, q)))
    order = desc(Vulnerability.date_added).nullslast() if kev else desc(Vulnerability.published_at).nullslast()
    statement = select(Vulnerability).where(*filters).order_by(order, Vulnerability.cve_id.desc())
    items, total = _page(db, statement, page, page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/api/v1/vulnerabilities/{cve_id}", response_model=VulnerabilityDetail)
def vulnerability_detail(cve_id: Annotated[str, Path(pattern=r"(?i)^CVE-\d{4}-\d{4,7}$")], db: DB) -> Vulnerability:
    vulnerability = db.scalar(
        select(Vulnerability).where(Vulnerability.cve_id == cve_id.upper()).options(
            selectinload(Vulnerability.articles).selectinload(Article.source),
            selectinload(Vulnerability.articles).selectinload(Article.vulnerabilities),
        )
    )
    if vulnerability is None:
        raise HTTPException(404, "Vulnerability not found")
    return vulnerability


@router.get("/api/v1/tools", response_model=Page[ToolResponse])
def tools(
    db: DB,
    page: PageNumber = 1,
    page_size: PageSize = 25,
    language: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    min_stars: Annotated[int | None, Query(ge=0)] = None,
    q: Annotated[str | None, Query(min_length=2, max_length=200)] = None,
    sort: Literal["newest", "stars", "recently_pushed"] = "newest",
) -> Page[ToolResponse]:
    filters = []
    if language:
        filters.append(Tool.language == language)
    if min_stars is not None:
        filters.append(Tool.stars >= min_stars)
    if q:
        filters.append(or_(_contains(Tool.full_name, q), _contains(Tool.description, q)))
    order = {"newest": Tool.discovered_at.desc(), "stars": Tool.stars.desc(), "recently_pushed": Tool.pushed_at.desc()}[sort]
    items, total = _page(db, select(Tool).where(*filters).order_by(order), page, page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/api/v1/sources", response_model=list[SourceResponse])
def sources(db: DB) -> list[SourceResponse]:
    result = []
    for source in db.scalars(select(Source).order_by(Source.kind, Source.name)):
        latest = db.scalar(
            select(IngestionRun).where(IngestionRun.source_id == source.id).order_by(IngestionRun.started_at.desc()).limit(1)
        )
        result.append(
            SourceResponse.model_validate(source).model_copy(
                update={
                    "latest_run_status": latest.status if latest else None,
                    "latest_run_at": latest.finished_at if latest else None,
                }
            )
        )
    return result
