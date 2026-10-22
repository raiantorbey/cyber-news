from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_USER_AGENT_MARKERS = (
    "example.invalid",
    "localhost:3000",
    "127.0.0.1:3000",
    "github.com/signalwatch",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SIGNALWATCH_", env_file=".env", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://signalwatch:signalwatch@db/signalwatch"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    user_agent: str = "CyberNews/0.1 (+https://example.invalid/contact)"
    request_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    request_retries: int = Field(default=2, ge=0, le=5)
    ingestion_concurrency: int = Field(default=4, ge=1, le=16)
    github_token: str | None = None
    github_query: str = "topic:cybersecurity stars:>=5 pushed:>={since}"
    nvd_api_key: str | None = None
    rss_interval_seconds: int = Field(default=900, ge=60)
    nvd_interval_seconds: int = Field(default=3600, ge=60)
    cisa_interval_seconds: int = Field(default=3600, ge=60)
    github_interval_seconds: int = Field(default=3600, ge=60)
    freshness_threshold_seconds: int = Field(default=7200, ge=60)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def user_agent_is_placeholder(self) -> bool:
        """True when the provider-facing identity is still an unusable default.

        NVD and GitHub both require a User-Agent that names the application and
        carries a real operator contact. The shipped defaults cannot satisfy
        that, so callers warn instead of sending a placeholder upstream.
        """
        agent = self.user_agent.lower()
        return any(marker in agent for marker in PLACEHOLDER_USER_AGENT_MARKERS)


@lru_cache
def get_settings() -> Settings:
    return Settings()
