import json

from app.db.models import Classification, Scan, ScanQuery, SearchResult, UrlCheck
from app.reporting.excel_export import _load_scan_dataframe


def test_same_url_from_two_queries_collapses_to_one_row(db_session):
    scan = Scan(provider="brave")
    db_session.add(scan)
    db_session.flush()

    query_a = ScanQuery(scan_id=scan.id, query_text='"Seville 406" "Padre Island Rentals"')
    query_b = ScanQuery(scan_id=scan.id, query_text='"Seville 406" rental')
    db_session.add_all([query_a, query_b])
    db_session.flush()

    normalized_url = "https://pirentals.com/seville-406"
    db_session.add_all(
        [
            SearchResult(
                scan_id=scan.id,
                scan_query_id=query_a.id,
                position=3,
                provider="brave",
                title="Seville 406 - PIR",
                snippet="snippet a",
                original_url=normalized_url,
                normalized_url=normalized_url,
                domain="pirentals.com",
            ),
            SearchResult(
                scan_id=scan.id,
                scan_query_id=query_b.id,
                position=1,
                provider="brave",
                title="Seville 406 rental",
                snippet="snippet b (best position)",
                original_url=normalized_url,
                normalized_url=normalized_url,
                domain="pirentals.com",
            ),
        ]
    )
    db_session.add(
        UrlCheck(
            scan_id=scan.id,
            normalized_url=normalized_url,
            status_code=200,
            redirect_chain_json=json.dumps([normalized_url]),
            final_url=normalized_url,
            response_time_ms=100.0,
            accessible=True,
            robots_disallowed=False,
            page_text_checked=True,
        )
    )
    db_session.add(
        Classification(
            scan_id=scan.id,
            normalized_url=normalized_url,
            classification="Active PIR listing",
            confidence="High",
            mentions_seville_406=True,
            mentions_pir=True,
            mentions_franke=False,
            booking_language_detected=False,
            booking_status_text="No booking path detected",
            manual_review_flag=False,
            notes="",
        )
    )
    db_session.commit()

    df = _load_scan_dataframe(db_session, scan.id)

    assert len(df) == 1
    row = df.iloc[0]
    assert row["Best Rank Position"] == 1
    assert row["Snippet"] == "snippet b (best position)"
    assert set(row["Matched Queries"].split("; ")) == {
        '"Seville 406" "Padre Island Rentals"',
        '"Seville 406" rental',
    }


def test_distinct_urls_stay_separate_rows(db_session):
    scan = Scan(provider="brave")
    db_session.add(scan)
    db_session.flush()
    query = ScanQuery(scan_id=scan.id, query_text="q")
    db_session.add(query)
    db_session.flush()

    db_session.add_all(
        [
            SearchResult(
                scan_id=scan.id,
                scan_query_id=query.id,
                position=1,
                provider="brave",
                title="A",
                snippet="",
                original_url="https://a.example/1",
                normalized_url="https://a.example/1",
                domain="a.example",
            ),
            SearchResult(
                scan_id=scan.id,
                scan_query_id=query.id,
                position=2,
                provider="brave",
                title="B",
                snippet="",
                original_url="https://b.example/1",
                normalized_url="https://b.example/1",
                domain="b.example",
            ),
        ]
    )
    db_session.commit()

    df = _load_scan_dataframe(db_session, scan.id)
    assert len(df) == 2
    # No UrlCheck/Classification rows yet -> safe cautious defaults.
    assert set(df["Classification"]) == {"Unclear — manual review required"}
    assert set(df["Manual Review Flag"]) == {True}
