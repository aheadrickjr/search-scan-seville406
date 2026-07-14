"""SQLAlchemy models.

Design principle: every scan run writes NEW rows. Nothing from a prior scan
is ever updated or deleted. This keeps full history in the database and
makes scan-to-scan comparison (Phase 3) possible without any schema changes --
comparisons just join/diff rows across scan_id ordered by run_at.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    provider: Mapped[str] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    queries: Mapped[list["ScanQuery"]] = relationship(back_populates="scan")
    search_results: Mapped[list["SearchResult"]] = relationship(back_populates="scan")
    url_checks: Mapped[list["UrlCheck"]] = relationship(back_populates="scan")
    classifications: Mapped[list["Classification"]] = relationship(
        back_populates="scan"
    )


class ScanQuery(Base):
    __tablename__ = "scan_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), index=True)
    query_text: Mapped[str] = mapped_column(Text)
    raw_result_count: Mapped[int] = mapped_column(Integer, default=0)

    scan: Mapped["Scan"] = relationship(back_populates="queries")
    search_results: Mapped[list["SearchResult"]] = relationship(
        back_populates="scan_query"
    )


class SearchResult(Base):
    """One (query, URL) occurrence as returned by the search provider.

    The same normalized_url can appear multiple times per scan, once per
    query that surfaced it. Deduplication for reporting happens at read time
    (grouping by scan_id + normalized_url), so raw provider data is never
    lost.
    """

    __tablename__ = "search_results"
    __table_args__ = (
        UniqueConstraint(
            "scan_query_id", "normalized_url", name="uq_search_result_query_url"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), index=True)
    scan_query_id: Mapped[int] = mapped_column(
        ForeignKey("scan_queries.id"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(50))
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_url: Mapped[str] = mapped_column(Text)
    normalized_url: Mapped[str] = mapped_column(Text, index=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)

    scan: Mapped["Scan"] = relationship(back_populates="search_results")
    scan_query: Mapped["ScanQuery"] = relationship(back_populates="search_results")


class UrlCheck(Base):
    """Result of the HTTP reachability check for one URL within one scan."""

    __tablename__ = "url_checks"
    __table_args__ = (
        UniqueConstraint(
            "scan_id", "normalized_url", name="uq_url_check_scan_url"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), index=True)
    normalized_url: Mapped[str] = mapped_column(Text, index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redirect_chain_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    accessible: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    robots_disallowed: Mapped[bool] = mapped_column(Boolean, default=False)
    page_text_checked: Mapped[bool] = mapped_column(Boolean, default=False)

    scan: Mapped["Scan"] = relationship(back_populates="url_checks")


class Classification(Base):
    """Deterministic rule-engine output for one URL within one scan."""

    __tablename__ = "classifications"
    __table_args__ = (
        UniqueConstraint(
            "scan_id", "normalized_url", name="uq_classification_scan_url"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), index=True)
    normalized_url: Mapped[str] = mapped_column(Text, index=True)
    classification: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[str] = mapped_column(String(20))
    mentions_seville_406: Mapped[bool] = mapped_column(Boolean, default=False)
    mentions_pir: Mapped[bool] = mapped_column(Boolean, default=False)
    mentions_franke: Mapped[bool] = mapped_column(Boolean, default=False)
    booking_language_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    booking_status_text: Mapped[str] = mapped_column(String(100))
    manual_review_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    scan: Mapped["Scan"] = relationship(back_populates="classifications")
