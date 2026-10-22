from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.models import RunStatus, SourceKind


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SourceBrief(APIModel):
    id: int
    name: str
    kind: SourceKind


class ArticleSummary(APIModel):
    id: int
    title: str
    canonical_url: str
    excerpt: str | None
    author: str | None
    category: str
    cve_ids: list[str]
    published_at: datetime
    image_url: str | None = None
    has_image: bool
    source: SourceBrief


class VulnerabilityBrief(APIModel):
    cve_id: str
    severity: str | None
    cvss_score: float | None
    kev: bool
    source_references: list["SourceReference"]


class SourceReference(BaseModel):
    source: str
    url: str


class ArticleDetail(ArticleSummary):
    vulnerabilities: list[VulnerabilityBrief]


class VulnerabilitySummary(VulnerabilityBrief):
    description: str | None
    vendor: str | None
    product: str | None
    published_at: datetime | None
    date_added: datetime | None
    due_date: datetime | None


class VulnerabilityDetail(VulnerabilitySummary):
    modified_at: datetime | None
    required_action: str | None
    articles: list[ArticleSummary]


class ToolResponse(APIModel):
    id: int
    full_name: str
    url: str
    description: str | None
    language: str | None
    stars: int
    forks: int
    topics: list[str]
    pushed_at: datetime | None
    discovered_at: datetime


class SourceResponse(SourceBrief):
    url: str
    enabled: bool
    last_success_at: datetime | None
    latest_run_status: RunStatus | None = None
    latest_run_at: datetime | None = None


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)


class OverviewResponse(BaseModel):
    article_count_24h: int
    vulnerability_count_7d: int
    kev_count: int
    tool_count_7d: int
    latest_articles: list[ArticleSummary]
    urgent_vulnerabilities: list[VulnerabilitySummary]
    latest_tools: list[ToolResponse]


class HealthResponse(BaseModel):
    status: str
    database: str
    ingestion: str
    last_ingestion_at: datetime | None
