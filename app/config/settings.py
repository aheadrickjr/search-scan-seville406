"""Environment-backed application settings."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    brave_api_key: str = Field(default="")
    database_path: Path = Field(default=REPO_ROOT / "data" / "scans.db")
    contact_email: str = Field(default="you@example.com")
    link_validator_rate_limit_seconds: float = Field(default=1.0)
    link_validator_timeout_seconds: float = Field(default=15.0)
    search_results_per_query: int = Field(default=20)
    queries_path: Path = Field(default=REPO_ROOT / "config" / "queries.yaml")
    domains_path: Path = Field(default=REPO_ROOT / "config" / "domains.yaml")

    @property
    def user_agent(self) -> str:
        return (
            "Seville406ListingScanner/1.0 "
            f"(evidence-gathering research tool; contact: {self.contact_email})"
        )


def load_settings(env_file: Path | None = None) -> Settings:
    load_dotenv(dotenv_path=env_file or (REPO_ROOT / ".env"))

    database_path = Path(os.getenv("DATABASE_PATH", "data/scans.db"))
    if not database_path.is_absolute():
        database_path = REPO_ROOT / database_path

    return Settings(
        brave_api_key=os.getenv("BRAVE_API_KEY", ""),
        database_path=database_path,
        contact_email=os.getenv("CONTACT_EMAIL", "you@example.com"),
        link_validator_rate_limit_seconds=float(
            os.getenv("LINK_VALIDATOR_RATE_LIMIT_SECONDS", "1.0")
        ),
        link_validator_timeout_seconds=float(
            os.getenv("LINK_VALIDATOR_TIMEOUT_SECONDS", "15")
        ),
        search_results_per_query=int(os.getenv("SEARCH_RESULTS_PER_QUERY", "20")),
    )
