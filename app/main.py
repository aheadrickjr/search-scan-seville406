"""CLI entrypoint.

Usage:
    python -m app.main scan                      # run a full scan + export
    python -m app.main export --scan-id 3         # re-export an existing scan
    python -m app.main list-scans                 # show scan history
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.classifier.rules import ClassificationResult, classify, mark_duplicates
from app.config.loader import load_domains, load_queries
from app.config.settings import REPO_ROOT, load_settings
from app.db.models import Classification, Scan, ScanQuery, SearchResult, UrlCheck
from app.db.session import make_session_factory
from app.link_validator.robots import RobotsCache
from app.link_validator.validator import LinkValidator
from app.reporting.excel_export import export_scan_to_excel
from app.search_provider.brave import BraveSearchProvider, SearchProviderError
from app.url_utils.normalize import extract_domain, normalize_url


def run_scan(settings) -> int:
    queries = load_queries(settings.queries_path)
    domains = load_domains(settings.domains_path)

    provider = BraveSearchProvider(
        api_key=settings.brave_api_key,
        user_agent=settings.user_agent,
        min_seconds_between_requests=1.0,
        timeout_seconds=settings.link_validator_timeout_seconds,
    )
    robots_cache = RobotsCache(user_agent=settings.user_agent)
    validator = LinkValidator(
        user_agent=settings.user_agent,
        robots_cache=robots_cache,
        min_seconds_between_requests=settings.link_validator_rate_limit_seconds,
        timeout_seconds=settings.link_validator_timeout_seconds,
    )

    session_factory = make_session_factory(settings.database_path)
    with session_factory() as session:
        scan = Scan(provider=provider.name)
        session.add(scan)
        session.flush()

        url_meta: dict[str, dict] = {}

        for query_text in queries:
            scan_query = ScanQuery(scan_id=scan.id, query_text=query_text)
            session.add(scan_query)
            session.flush()

            try:
                raw_results = provider.search(
                    query_text, count=settings.search_results_per_query
                )
            except SearchProviderError as exc:
                print(f"[warn] query {query_text!r} failed: {exc}", file=sys.stderr)
                scan_query.raw_result_count = 0
                continue

            scan_query.raw_result_count = len(raw_results)
            for raw in raw_results:
                normalized_url = normalize_url(raw.url)
                domain = extract_domain(normalized_url)
                session.add(
                    SearchResult(
                        scan_id=scan.id,
                        scan_query_id=scan_query.id,
                        position=raw.position,
                        provider=provider.name,
                        title=raw.title,
                        snippet=raw.snippet,
                        original_url=raw.url,
                        normalized_url=normalized_url,
                        domain=domain,
                    )
                )
                meta = url_meta.setdefault(
                    normalized_url,
                    {
                        "domain": domain,
                        "title": raw.title,
                        "snippet": raw.snippet,
                        "position": raw.position,
                    },
                )
                if raw.position < meta["position"]:
                    meta.update(
                        {"title": raw.title, "snippet": raw.snippet, "position": raw.position}
                    )

        session.flush()
        print(f"Collected {len(url_meta)} unique URLs across {len(queries)} queries.")

        classifications_by_url: dict[str, ClassificationResult] = {}
        for normalized_url, meta in url_meta.items():
            check_result = validator.check(normalized_url)
            session.add(
                UrlCheck(
                    scan_id=scan.id,
                    normalized_url=normalized_url,
                    status_code=check_result.status_code,
                    redirect_chain_json=json.dumps(check_result.redirect_chain),
                    final_url=check_result.final_url,
                    response_time_ms=check_result.response_time_ms,
                    accessible=check_result.accessible,
                    error_message=check_result.error_message,
                    robots_disallowed=check_result.robots_disallowed,
                    page_text_checked=check_result.page_text_checked,
                )
            )
            classifications_by_url[normalized_url] = classify(
                normalized_url=normalized_url,
                title=meta["title"] or "",
                snippet=meta["snippet"] or "",
                domains=domains,
                url_check=check_result,
            )

        dupe_rows = [
            (url, meta["domain"], meta["title"] or "", meta["position"])
            for url, meta in url_meta.items()
        ]
        classifications_by_url = mark_duplicates(dupe_rows, classifications_by_url)

        for normalized_url, clas in classifications_by_url.items():
            session.add(
                Classification(
                    scan_id=scan.id,
                    normalized_url=normalized_url,
                    classification=clas.classification,
                    confidence=clas.confidence,
                    mentions_seville_406=clas.mentions_seville_406,
                    mentions_pir=clas.mentions_pir,
                    mentions_franke=clas.mentions_franke,
                    mentions_only_in_hidden_metadata=clas.mentions_only_in_hidden_metadata,
                    booking_language_detected=clas.booking_language_detected,
                    booking_status_text=clas.booking_status_text,
                    manual_review_flag=clas.manual_review_flag,
                    notes=clas.notes,
                )
            )

        session.commit()

        output_path = REPO_ROOT / "reports" / f"evidence_register_scan_{scan.id}.xlsx"
        export_scan_to_excel(session, scan.id, output_path)
        print(f"Scan {scan.id} complete. Evidence register written to {output_path}")
        return scan.id


def run_export(settings, scan_id: int, output: Path | None) -> Path:
    session_factory = make_session_factory(settings.database_path)
    with session_factory() as session:
        output_path = output or (
            REPO_ROOT / "reports" / f"evidence_register_scan_{scan_id}.xlsx"
        )
        path = export_scan_to_excel(session, scan_id, output_path)
        print(f"Evidence register written to {path}")
        return path


def run_list_scans(settings) -> None:
    session_factory = make_session_factory(settings.database_path)
    with session_factory() as session:
        scans = session.execute(select(Scan).order_by(Scan.run_at)).scalars().all()
        if not scans:
            print("No scans recorded yet.")
            return
        for scan in scans:
            result_count = session.execute(
                select(SearchResult).where(SearchResult.scan_id == scan.id)
            ).scalars().all()
            unique_urls = {r.normalized_url for r in result_count}
            print(
                f"scan_id={scan.id}  run_at={scan.run_at}  provider={scan.provider}  "
                f"unique_urls={len(unique_urls)}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seville 406 Legacy Listing Scanner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan", help="Run a new scan and export the evidence register")

    export_parser = subparsers.add_parser("export", help="Export an existing scan to Excel")
    export_parser.add_argument("--scan-id", type=int, required=True)
    export_parser.add_argument("--output", type=Path, default=None)

    subparsers.add_parser("list-scans", help="List all recorded scans")

    args = parser.parse_args(argv)
    settings = load_settings()

    if args.command == "scan":
        run_scan(settings)
    elif args.command == "export":
        run_export(settings, args.scan_id, args.output)
    elif args.command == "list-scans":
        run_list_scans(settings)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
