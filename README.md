# Seville 406 Legacy Listing Scanner (Phase 1 + Phase 2)

A local tool that finds, records, and tracks search results and listings
that still associate **Seville Condominium Unit 406** (South Padre Island,
TX) with its former manager, **Padre Island Rentals ("PIR")**, instead of
the current manager, **Franke Rentals** -- so there's an organized,
timestamped evidence register for outreach and follow-up.

This includes **Phase 1** (search + HTTP-level evidence pipeline) and
**Phase 2** (real headless-browser validation + screenshots) of a
five-phase roadmap (see [Roadmap](#roadmap) below). It still does not use
AI classification or scheduling, and it never estimates or implies lost
revenue -- its job is to document visibility, attribution, link condition,
and change over time.

## What it does

1. Runs a configurable list of search queries against the **Brave Search
   API**.
2. Collects organic results: title, URL, snippet, rank position.
3. Deduplicates results by normalized URL.
4. Checks each URL in a real **headless Chromium browser** (Playwright):
   status code, redirect chain, final URL, response time, reachability --
   and because it's a real browser, this also sees JavaScript-rendered
   content (booking widgets, availability calendars) that a plain HTTP
   request can't.
5. Captures a full-page **screenshot** of every reachable result, saved to
   `screenshots/<scan_id>/` and referenced from the report.
6. Reads page text *and* hidden metadata (`<title>`, meta tags, JSON-LD,
   image alt text) for manager-name/property mentions -- catching
   references that were never cleaned up from a page's metadata even after
   its visible copy was updated.
7. Applies **deterministic, rule-based** classification (no AI/LLM) using
   domain lists, text matches, and HTTP outcome.
8. Stores every scan in SQLite, **appending** -- prior scans are never
   overwritten, so history accumulates run over run.
9. Exports a structured Excel workbook (the evidence register) for the
   current scan.

## Setup

### 1. Prerequisites

- Python 3.12 (Windows, macOS, or Linux)
- A Brave Search API key (see below)
- ~300MB free disk space for Playwright's Chromium browser (downloaded
  automatically on first run)

### 2. Get a Brave Search API key

1. Go to <https://api.search.brave.com/app/keys> and sign up (Brave account
   required).
2. Subscribe to the **Free** plan (2,000 queries/month at time of writing)
   or a paid plan if you expect to run more scans -- a full scan of the
   default query list uses ~17 queries.
3. Create an API key ("Add key") and copy it.
4. In this project's root, copy `.env.example` to `.env`:
   ```
   cp .env.example .env        # macOS/Linux
   Copy-Item .env.example .env # Windows PowerShell
   ```
5. Paste your key into `.env` as `BRAVE_API_KEY=...`.
6. Set `CONTACT_EMAIL` in `.env` to an email you control -- it's embedded
   in the User-Agent header sent to third-party sites during link
   validation, so a site owner can identify/contact the tool's operator if
   needed.

### 3. Windows setup

From the project root in PowerShell:

```powershell
.\scripts\start.ps1
```

This creates a virtual environment, installs dependencies, downloads
Playwright's Chromium browser (~300MB, one-time), copies `.env.example` to
`.env` on first run (edit it before continuing), and runs a scan. Other
commands:

```powershell
.\scripts\start.ps1 -Command sample-report   # generate the mock-data sample report
.\scripts\start.ps1 -Command list-scans      # list all past scans
.\scripts\start.ps1 -Command export -ScanId 3
```

If PowerShell blocks the script from running, allow it for the current
session first:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 4. macOS/Linux setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # one-time browser download
cp .env.example .env          # then edit .env with your BRAVE_API_KEY
python -m app.main scan
```

## Running it

```bash
python -m app.main scan                    # run a new scan + export
python -m app.main list-scans              # show scan history
python -m app.main export --scan-id 3      # re-export an existing scan
python scripts/generate_sample_report.py   # mock-data sample report (no network calls)
```

Each scan writes to `data/scans.db` (SQLite), saves screenshots to
`screenshots/<scan_id>/`, and exports an Excel workbook to
`reports/evidence_register_scan_<id>.xlsx`.

Because each URL is now checked with a real browser, a scan takes longer
than a plain HTTP check would (roughly a few seconds per URL). Progress is
printed to the console as it goes (`[N/total] checking <url>`).

> **Note on schema changes:** there's no migration tool in Phase 1 (by
> design -- see recommended stack). If you pull an update that adds a new
> database column (as this project has already done once), your existing
> `data/scans.db` won't have it and inserts will fail with a "no such
> column" error. Delete `data/scans.db` and re-run a scan to get a fresh
> schema -- your past scans' exported `.xlsx` files in `reports/` aren't
> affected, only the database's own history.

## Configuration

Edit these without touching code:

- **`config/queries.yaml`** -- the list of search queries run every scan.
- **`config/domains.yaml`** -- domain classification lists: `pir_domains`
  (former manager), `franke_domains` (current manager), `ota_domains`
  (third-party listing sites of interest). Classification depends entirely
  on these lists, so add any additional domains you discover.

Other tunables live in `.env` (rate limiting, timeouts, results per query --
see `.env.example` for the full list with comments).

## The evidence register (Excel workbook)

Each export has six sheets:

1. **Executive Summary** -- scan date, total unique results, PIR-associated
   count, active/dead/redirect counts, results with booking controls
   detected, Franke count, manual-review count, and how many results were
   checked via real browser render (screenshots available).
2. **Current Results** -- every unique result with all captured fields,
   including whether it was browser-rendered and its screenshot path.
3. **PIR-Associated Listings** -- filtered to PIR-attributed results.
4. **Franke Listings** -- filtered to Franke-attributed results.
5. **Link Validation** -- status codes, redirect chains, final URLs,
   accessibility, rendered flag, screenshot path, classification.
6. **Manual Review** -- anything flagged uncertain or blocked.

A sample workbook built from fabricated data (no network calls) is at
`sample_output/sample_evidence_register.xlsx` -- regenerate it any time with
`python scripts/generate_sample_report.py`.

### Classification categories

`Active PIR listing`, `Active third-party listing attributed to PIR`,
`Dead PIR page`, `Redirect to PIR inventory`, `Redirect to unrelated
property`, `OTA page, no availability signal detected`, `Apparently
bookable listing`, `Franke Rentals listing`, `Duplicate`, `Search result
only (no page content confirms property)`, `Blocked or inaccessible`,
`Unclear — manual review required`.

All of these come from **deterministic rules** in `app/classifier/rules.py`
(domain matches, HTTP status, redirect target, keyword matches) -- there is
no AI/LLM involved in Phase 1.

Booking status always uses cautious language: *"Booking controls
detected," "No booking path detected," "Unable to determine (...)"* --
never a flat assertion that a listing is or isn't bookable.

### Hidden-metadata detection

Beyond the visible page text, the link validator also reads `<title>`,
`<meta name="description"/"keywords">`, Open Graph/Twitter Card tags,
`<script type="application/ld+json">` structured data, and image `alt`
text -- none of which a site visitor sees, but all of which search engines
and OTA platforms index directly. When a Seville 406/PIR reference shows up
in that metadata but *not* in the visible page copy, the result is flagged
**"Mentions Only In Hidden Metadata"** with a note explaining the
implication: the visible page was likely updated, but the underlying page
metadata wasn't, which is a concrete, documentable reason stale
attribution keeps resurfacing in search results even after a listing looks
"cleaned up" to a human visitor.

### Screenshots

Every reachable, robots.txt-allowed result gets a full-page PNG screenshot
at scan time, saved to `screenshots/<scan_id>/<domain>__<url-slug>.png` and
referenced by relative path in the **Screenshot Path** column (Current
Results and Link Validation sheets). This is durable, dated visual
evidence beyond text -- useful on its own for an outreach package, and it
means you don't have to re-visit a stale link later to see what it looked
like at scan time.

## Current limitations (read before relying on this for anything)

- **Aggressive anti-bot defenses can still block a real browser.** Playwright
  renders like a genuine browser, which resolves most JavaScript-rendering
  gaps, but sites using advanced fingerprinting/challenge systems (e.g.
  Cloudflare's bot-management challenge pages) may still block or serve a
  CAPTCHA to an automated browser. Per the project's compliance ground
  rules, this tool does **not** attempt to solve CAPTCHAs or otherwise
  evade such defenses -- a block is recorded as `Blocked or inaccessible`
  and left alone.
- **Bot-blocking.** Many OTAs return 401/403/429/999-style responses. These
  are recorded as `Blocked or inaccessible`, not `Dead PIR page` -- a block
  is not evidence a page is gone.
- **No manual-review workflow yet.** Results flagged for manual review are
  visible in the "Manual Review" sheet, but there's no way (yet) to record
  your review/correction back into the tool -- that's still on the Phase 2
  roadmap. Corrections you make today live only in your copy of the Excel
  file and won't carry forward to the next scan.
- **Duplicate detection is a simple heuristic.** Only catches duplicates
  that share the exact same domain and exact same title after URL
  normalization. Near-duplicates with different titles won't be caught.
- **Domain extraction is a simple last-two-labels heuristic**, not a full
  public-suffix-list implementation -- fine for the `.com` domains this
  project targets, but it will mis-extract domains with multi-part TLDs
  (e.g. `.co.uk`).
- **Rank positions will shift scan to scan.** This is expected (search
  results change over time), not a bug -- it's why every scan is stored
  immutably rather than overwritten.
- **Scans are slower now.** A real browser navigation per URL takes a few
  seconds each, versus a near-instant plain HTTP request. Expect a full
  scan to take a few minutes rather than under a minute.
- No scan-to-scan comparison, HTML executive report, or Action Register
  yet -- the database schema is append-only and designed to support this
  in Phase 3, but the comparison logic itself isn't built.

## Compliance notes

- **Search provider.** Uses the Brave Search API only -- a sanctioned JSON
  API, not a scraper of Google/Bing search result pages.
- **Link validation and robots.txt.** For every URL, the app always
  records HTTP status, redirect chain, and reachability, regardless of
  robots.txt (resolving a URL you already have is normal client behavior).
  It only skips reading a page's **rendered text and screenshot** (for
  keyword/booking-language matching) when that URL's `robots.txt`
  disallows the path for this tool's user-agent -- those results are
  flagged for manual review instead of guessed at.
- **Rate limiting.** Requests to the same domain during link validation are
  throttled (default: 1 request/second, configurable via
  `LINK_VALIDATOR_RATE_LIMIT_SECONDS` in `.env`). The Brave Search API
  calls are similarly throttled.
- **Identification.** The headless browser sends a descriptive
  `User-Agent` including a contact email (`CONTACT_EMAIL` in `.env`), so a
  site owner can identify and reach the tool's operator if they have a
  concern. This is a real, disclosed identifier, not a spoofed one.
- **No anti-bot evasion.** If a site blocks or challenges the request,
  that's recorded as `Blocked or inaccessible` and left alone -- no
  CAPTCHA-solving, fingerprint spoofing, or other bypass techniques.
  Rendering with a real browser is done for legitimate visibility (seeing
  what a real visitor sees), not to defeat a site's bot defenses.
- **Data minimization.** Only short text snippets/keyword flags and a
  per-URL screenshot are stored, not full page HTML archives. No personal
  data about any individual is collected -- this tool tracks a rental
  unit's listings, not people. No third-party LLM is used, so no page
  content leaves your machine except to the Brave Search API (query text
  only) and to the sites being checked (ordinary browser requests).

## Tests

```bash
python -m pytest tests/ -v
```

Covers URL normalization/deduplication, the classification rule engine
(one domain/scenario combination per category, including rendered vs.
HTTP-only booking-status behavior), dedupe behavior in the report-building
layer, and the browser validator's pure helper functions (redirect-chain
building, filename sanitization).

## Project layout

```
app/
  config/              settings + YAML config loaders
  search_provider/     provider adapter interface + Brave implementation
  url_utils/           URL normalization / domain extraction
  link_validator/      HTTP-only checks, robots.txt cache, rate limiting
                        (kept for reference; not used by default -- see
                        browser_validator/)
  browser_validator/    Playwright-based checks, screenshots, rendered
                        text/metadata extraction
  classifier/           deterministic rule engine
  db/                   SQLAlchemy models + session
  reporting/             Excel workbook builder
  main.py                CLI entrypoint
config/
  queries.yaml         editable search queries
  domains.yaml         editable domain classification lists
scripts/
  start.ps1            Windows setup/run script
  generate_sample_report.py   mock-data sample report generator
tests/                 pytest suite
sample_output/         sample_evidence_register.xlsx (generated, mock data)
screenshots/           per-scan screenshot PNGs (created at scan time)
```

## Roadmap

- **Phase 2** -- Playwright-based browser validation and screenshots are
  now built (this update). Still outstanding from the original Phase 2
  scope: a manual-review workflow for recording your corrections back into
  the tool.
- **Phase 3** -- scan-to-scan comparison (new/removed/changed results,
  ranking shifts, status changes), an HTML executive report, an Action
  Register, scheduled scans.
- **Phase 4** -- optional LLM-assisted classification for ambiguous results
  only, with confidence scores and mandatory human approval before
  anything is finalized. No private keys, payment data, or unnecessary
  personal data would be sent to any LLM.
- **Phase 5** -- a Streamlit UI for running scans, filtering results,
  reviewing evidence, correcting classifications, assigning follow-up
  owners, and exporting reports. Manual corrections would persist and
  never be overwritten by later scans.
