# Private Credit Monitor Report

## Summary
- generated_at_utc: `2026-03-15T07:11:21Z`
- script: `build_private_credit_monitor.py`
- script_version: `v1.12-yf`
- out_dir: `private_credit_cache`
- proxy_signal: **WATCH**
- structural_signal: **WATCH**
- combined_signal: **WATCH**
- signal_basis: `MIXED`
- overall_confidence: `PARTIAL`
- reasons: `proxy:bdc_basket_median_ret5<=-4 AND below_ma20_share>=80%; structural:fresh_nav_median_discount<=-10 with coverage>=3`
- tags: `proxy:MARKET_PROXY_WEAK,structural:NAV_DISCOUNT_WIDE`

## 1) BDC Market Proxy
- proxy_price_basis: `Adj Close (yfinance)`
- nav_overlay_market_price_basis: `raw Close (yfinance)`
- coverage: `5`
- median_ret1_pct: `-0.363967`
- median_ret5_pct: `-4.53357`
- median_z60: `-1.874566`
- median_drawdown_20d_pct: `-8.060454`
- extreme_z_count: `1`
- extreme_z_share: `20.0`
- ret5_le_minus5_count: `2`
- ret5_le_minus5_share: `40.0`
- below_ma20_count: `5`
- below_ma20_share: `100.0`

| ticker | class | proxy_close | raw_close | basis | data_date | ret1% | ret5% | z60 | p60 | p252 | dd20% | px_vs_ma20% | div30 | div_events30 | source | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ARCC | BDC | 17.860001 | 17.860001 | Adj Close | 2026-03-13 | 1.534966 | -2.095153 | -1.874566 | 3.333333 | 1.587302 | -5.959157 | -3.105301 | 0.480000 | 1 | yfinance://ARCC?start=2024-07-23&end=2026-03-16&interval=1d&auto_adjust=false&actions=true | OK\|proxy_basis=Adj Close\|div_events30=1\|div30=0.48 |
| BXSL | BDC | 23.650000 | 23.650000 | Adj Close | 2026-03-13 | -0.253056 | -0.713686 | -1.602224 | 3.333333 | 0.793651 | -4.056795 | -1.765318 | 0.000000 | 0 | yfinance://BXSL?start=2024-07-23&end=2026-03-16&interval=1d&auto_adjust=false&actions=true | OK\|proxy_basis=Adj Close |
| FSK | BDC | 10.090000 | 10.090000 | Adj Close | 2026-03-13 | -1.464840 | -5.612717 | -2.230994 | 1.666667 | 0.396825 | -24.813710 | -13.771737 | 0.000000 | 0 | yfinance://FSK?start=2024-07-23&end=2026-03-16&interval=1d&auto_adjust=false&actions=true | OK\|proxy_basis=Adj Close |
| OBDC | BDC | 10.950000 | 10.950000 | Adj Close | 2026-03-13 | -0.363967 | -4.533570 | -1.907789 | 3.333333 | 0.793651 | -8.060454 | -4.345929 | 0.000000 | 0 | yfinance://OBDC?start=2024-07-23&end=2026-03-16&interval=1d&auto_adjust=false&actions=true | OK\|proxy_basis=Adj Close |
| PSEC | BDC | 2.560000 | 2.560000 | Adj Close | 2026-03-13 | -3.396232 | -6.227109 | -0.714509 | 21.666667 | 32.539683 | -14.723820 | -7.559497 | 0.045000 | 1 | yfinance://PSEC?start=2024-07-23&end=2026-03-16&interval=1d&auto_adjust=false&actions=true | OK\|proxy_basis=Adj Close\|div_events30=1\|div30=0.045 |
| BIZD | ETF_PROXY | 12.480000 | 12.480000 | Adj Close | 2026-03-13 | -0.239814 | -2.727984 | -2.076790 | 1.666667 | 0.396825 | -7.142858 | -4.029532 | 0.000000 | 0 | yfinance://BIZD?start=2024-07-23&end=2026-03-16&interval=1d&auto_adjust=false&actions=true | OK\|proxy_basis=Adj Close |

## 2) NAV Overlay (manual + auto SEC, optional)
- path: `private_credit_cache/inputs/manual_nav.json`
- as_of_date: `YYYY-MM-DD`
- confidence: `OK`
- raw_row_count: `1`
- template_excluded_count: `1`
- manual_valid_count: `0`
- auto_enabled: `True`
- auto_source: `sec_xbrl_first_v1_docscan_fallback_v1.12`
- auto_attempted_count: `5`
- auto_found_count: `5`
- manual_override_tickers: `[]`
- coverage_total: `3`
- coverage_fresh: `3`
- median_discount_pct_fresh: `-12.147103`
- median_discount_pct_all: `-12.147103`

### Coverage decomposition
- auto_total_count: `5`
- auto_used_in_stats_count: `3`
- auto_review_count: `2`
- auto_excluded_count: `0`
- auto_review_only_count: `2`
- manual_used_in_stats_count: `0`
- manual_invalid_count: `1`
- effective_auto_count: `3`
- effective_manual_count: `0`
- effective_structural_count: `3`
- effective_structural_fresh_count: `3`

| ticker | source_kind | doc_name | doc_score | doc_period_anchor | candidate_role | date_binding_mode | extraction_method | used_in_stats | dq_status | review_flag | match_score | matched_pattern | price_obs_date | nav_ref_date | nav_date_used | nav_date_source | filing_date | market_close | market_date | premium_discount_pct | nav_age_days | fresh_for_rule | source | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ARCC | auto_sec | us-gaap:NetAssetValuePerShare | 250 | 2025-12-31 | current_xbrl_standard_concept | xbrl_fact_end_date | xbrl_companyconcept | True | OK | NONE | 20.000000 | us-gaap:NetAssetValuePerShare | NA | 2025-12-31 | 2025-12-31 | xbrl_fact_end_date | 2026-02-04 | 17.860001 | 2026-03-13 | -10.431289 | 72 | True | https://data.sec.gov/api/xbrl/companyconcept/CIK0001287750/us-gaap/NetAssetValuePerShare.json | auto_xbrl:xbrl_companyconcept:us-gaap:NetAssetValuePerShare:filed=2026-02-04:end=2025-12-31 |
| BXSL | auto_sec | us-gaap:NetAssetValuePerShare | 250 | 2025-12-31 | current_xbrl_standard_concept | xbrl_fact_end_date | xbrl_companyconcept | True | OK | NONE | 20.000000 | us-gaap:NetAssetValuePerShare | NA | 2025-12-31 | 2025-12-31 | xbrl_fact_end_date | 2026-02-25 | 23.650000 | 2026-03-13 | -12.147103 | 72 | True | https://data.sec.gov/api/xbrl/companyconcept/CIK0001736035/us-gaap/NetAssetValuePerShare.json | auto_xbrl:xbrl_companyconcept:us-gaap:NetAssetValuePerShare:filed=2026-02-25:end=2025-12-31 |
| OBDC | auto_sec | us-gaap:NetAssetValuePerShare | 250 | 2025-12-31 | current_xbrl_standard_concept | xbrl_fact_end_date | xbrl_companyconcept | True | OK | NONE | 20.000000 | us-gaap:NetAssetValuePerShare | NA | 2025-12-31 | 2025-12-31 | xbrl_fact_end_date | 2026-02-18 | 10.950000 | 2026-03-13 | -26.063471 | 72 | True | https://data.sec.gov/api/xbrl/companyconcept/CIK0001655888/us-gaap/NetAssetValuePerShare.json | auto_xbrl:xbrl_companyconcept:us-gaap:NetAssetValuePerShare:filed=2026-02-18:end=2025-12-31 |
| ARCC | manual | NA | NA | NA | manual | manual_input | manual | False | MANUAL_INVALID | NONE | NA | NA | NA | NA | NA | manual_input | NA | 17.860001 | 2026-03-13 | NA | NA | False | https://example.com/investor-relations | Reported NAV per share |
| FSK | auto_sec | us-gaap:NetAssetValuePerShare | 250 | 2025-12-31 | current_xbrl_standard_concept | xbrl_fact_end_date | xbrl_companyconcept | False | REVIEW_DISCOUNT_DEEP | DISCOUNT_LE_-45 | 20.000000 | us-gaap:NetAssetValuePerShare | NA | 2025-12-31 | 2025-12-31 | xbrl_fact_end_date | 2026-02-25 | 10.090000 | 2026-03-13 | -51.699378 | 72 | True | https://data.sec.gov/api/xbrl/companyconcept/CIK0001422183/us-gaap/NetAssetValuePerShare.json | auto_xbrl:xbrl_companyconcept:us-gaap:NetAssetValuePerShare:filed=2026-02-25:end=2025-12-31 |
| PSEC | auto_sec | us-gaap:NetAssetValuePerShare | 250 | 2025-12-31 | current_xbrl_standard_concept | xbrl_fact_end_date | xbrl_companyconcept | False | REVIEW_DISCOUNT_DEEP | DISCOUNT_LE_-45 | 20.000000 | us-gaap:NetAssetValuePerShare | NA | 2025-12-31 | 2025-12-31 | xbrl_fact_end_date | 2026-02-09 | 2.560000 | 2026-03-13 | -58.776167 | 72 | True | https://data.sec.gov/api/xbrl/companyconcept/CIK0001287032/us-gaap/NetAssetValuePerShare.json | auto_xbrl:xbrl_companyconcept:us-gaap:NetAssetValuePerShare:filed=2026-02-09:end=2025-12-31 |

### NAV auto match snippets
- ARCC | used_in_stats=True | dq_status=OK | doc=us-gaap:NetAssetValuePerShare | doc_score=250 | candidate_role=current_xbrl_standard_concept | date_binding_mode=xbrl_fact_end_date | score=20.0 | pattern=us-gaap:NetAssetValuePerShare | method=xbrl_companyconcept
  - snippet: `XBRL fact us-gaap:NetAssetValuePerShare end=2025-12-31 val=19.94 unit=USD/shares`
  - nav_ref_match: `2025-12-31`
  - doc_period_anchor_match: `2025-12-31`
  - local_role_ctx: `Net Asset Value Per Share`
  - section_bonus: `xbrl_api`
  - xbrl: `us-gaap:NetAssetValuePerShare | unit=USD/shares`
- BXSL | used_in_stats=True | dq_status=OK | doc=us-gaap:NetAssetValuePerShare | doc_score=250 | candidate_role=current_xbrl_standard_concept | date_binding_mode=xbrl_fact_end_date | score=20.0 | pattern=us-gaap:NetAssetValuePerShare | method=xbrl_companyconcept
  - snippet: `XBRL fact us-gaap:NetAssetValuePerShare end=2025-12-31 val=26.92 unit=USD/shares`
  - nav_ref_match: `2025-12-31`
  - doc_period_anchor_match: `2025-12-31`
  - local_role_ctx: `Net Asset Value Per Share`
  - section_bonus: `xbrl_api`
  - xbrl: `us-gaap:NetAssetValuePerShare | unit=USD/shares`
- OBDC | used_in_stats=True | dq_status=OK | doc=us-gaap:NetAssetValuePerShare | doc_score=250 | candidate_role=current_xbrl_standard_concept | date_binding_mode=xbrl_fact_end_date | score=20.0 | pattern=us-gaap:NetAssetValuePerShare | method=xbrl_companyconcept
  - snippet: `XBRL fact us-gaap:NetAssetValuePerShare end=2025-12-31 val=14.81 unit=USD/shares`
  - nav_ref_match: `2025-12-31`
  - doc_period_anchor_match: `2025-12-31`
  - local_role_ctx: `Net Asset Value Per Share`
  - section_bonus: `xbrl_api`
  - xbrl: `us-gaap:NetAssetValuePerShare | unit=USD/shares`
- FSK | used_in_stats=False | dq_status=REVIEW_DISCOUNT_DEEP | doc=us-gaap:NetAssetValuePerShare | doc_score=250 | candidate_role=current_xbrl_standard_concept | date_binding_mode=xbrl_fact_end_date | score=20.0 | pattern=us-gaap:NetAssetValuePerShare | method=xbrl_companyconcept
  - snippet: `XBRL fact us-gaap:NetAssetValuePerShare end=2025-12-31 val=20.89 unit=USD/shares`
  - nav_ref_match: `2025-12-31`
  - doc_period_anchor_match: `2025-12-31`
  - local_role_ctx: `Net Asset Value Per Share`
  - section_bonus: `xbrl_api`
  - xbrl: `us-gaap:NetAssetValuePerShare | unit=USD/shares`
- PSEC | used_in_stats=False | dq_status=REVIEW_DISCOUNT_DEEP | doc=us-gaap:NetAssetValuePerShare | doc_score=250 | candidate_role=current_xbrl_standard_concept | date_binding_mode=xbrl_fact_end_date | score=20.0 | pattern=us-gaap:NetAssetValuePerShare | method=xbrl_companyconcept
  - snippet: `XBRL fact us-gaap:NetAssetValuePerShare end=2025-12-31 val=6.21 unit=USD/shares`
  - nav_ref_match: `2025-12-31`
  - doc_period_anchor_match: `2025-12-31`
  - local_role_ctx: `Net Asset Value Per Share`
  - section_bonus: `xbrl_api`
  - xbrl: `us-gaap:NetAssetValuePerShare | unit=USD/shares`

### NAV auto fetch notes
- ARCC:OK_XBRL:10-K:2026-02-04:doc=us-gaap:NetAssetValuePerShare:score=20.0:dq=OK:method=xbrl_companyconcept
- BXSL:OK_XBRL:10-K:2026-02-25:doc=us-gaap:NetAssetValuePerShare:score=20.0:dq=OK:method=xbrl_companyconcept
- OBDC:OK_XBRL:10-K:2026-02-18:doc=us-gaap:NetAssetValuePerShare:score=20.0:dq=OK:method=xbrl_companyconcept
- FSK:INFO:no_match_in_filing:8-K:2026-03-05:docs_scanned=3
- FSK:INFO:no_match_in_filing:8-K:2026-01-21:docs_scanned=4
- FSK:INFO:no_match_in_filing:8-K:2025-12-23:docs_scanned=5
- FSK:INFO:no_match_in_filing:8-K:2025-11-13:docs_scanned=3
- FSK:REVIEW_ONLY:10-K:2026-02-25:doc=us-gaap:NetAssetValuePerShare:doc_score=250:score=20.0:dq=REVIEW_DISCOUNT_DEEP:method=xbrl_companyconcept:nav_date_source=xbrl_fact_end_date:date_binding_mode=xbrl_fact_end_date
- PSEC:INFO:no_match_in_filing:8-K:2026-02-11:docs_scanned=5
- PSEC:INFO:no_match_in_filing:8-K:2026-02-09:docs_scanned=4
- PSEC:INFO:no_match_in_filing:8-K:2026-01-15:docs_scanned=3
- PSEC:INFO:no_match_in_filing:8-K:2025-11-06:docs_scanned=4
- PSEC:REVIEW_ONLY:10-Q:2026-02-09:doc=us-gaap:NetAssetValuePerShare:doc_score=250:score=20.0:dq=REVIEW_DISCOUNT_DEEP:method=xbrl_companyconcept:nav_date_source=xbrl_fact_end_date:date_binding_mode=xbrl_fact_end_date

## 3) Event Overlay (manual, optional)
- path: `private_credit_cache/inputs/manual_events.json`
- as_of_date: `YYYY-MM-DD`
- recent_window_days: `45`
- raw_row_count: `1`
- template_excluded_count: `1`
- event_count_total: `0`
- event_count_recent: `0`
- alert_recent_count: `0`
- watch_recent_count: `0`
- latest_recent_event_date: `None`

| event_date | category | entity | severity | is_recent | valid_for_stats | template_excluded | title | source | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NA | withdrawal_limit | Example fund / lender / platform | WATCH | False | False | True | Example title | https://example.com/article | Free-form note |

## 4) Public Credit Context (reference-only; not recomputed here)
- enabled: `True`
- source_path: `unified_dashboard/latest.json`
- reference_only: `True`

| series | source_module | signal | value | data_date | reason | tag |
| --- | --- | --- | --- | --- | --- | --- |
| BAMLH0A0HYM2 | fred_cache | WATCH | 3.170000 | 2026-03-12 | abs(Z60)>=2 | EXTREME_Z |
| HYG_IEF_RATIO | market_cache | NONE | 0.828539 | 2026-03-13 | NA | NA |
| OFR_FSI | market_cache | ALERT | -0.925000 | 2026-03-11 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_ZD,JUMP_RET |

## 5) Confidence / DQ
- price_confidence: `OK`
- nav_confidence: `OK`
- event_confidence: `TEMPLATE_ONLY`
- structural_confidence: `PARTIAL`
- overall_confidence: `PARTIAL`
- basket_coverage: `5`

## 6) Notes
- This module is display-only / advisory-only by design.
- HY spread / HYG-IEF / OFR_FSI are NOT recomputed here.
- Manual overlays are expected for event flags and may override auto NAV values.
- Template / invalid manual rows are excluded from coverage/count/median statistics.
- combined_signal should be interpreted together with signal_basis and structural_confidence.
- Public Credit Context mirrors unified signal from preferred source modules when available.
- Auto NAV from SEC excludes date-component contamination and all REVIEW rows from structural stats.
- Implied NAV extraction from price + premium/discount sentences is enabled to reduce false data loss.
- v1.12-yf uses yfinance daily history for BDC Market Proxy metrics on Adj Close.
- v1.12-yf preserves raw Close for NAV overlay premium/discount calculations.
- v1.12-yf uses SEC XBRL APIs as the first NAV extraction path (companyconcept first, companyfacts discovery second).
- v1.12-yf keeps HTML / regex extraction only as fallback when XBRL does not yield a usable NAV fact.
- v1.12-yf preserves SEC retry/backoff and optional cache for fetch stability.
- v1.12-yf preserves filing index doc scan as a fallback path instead of primaryDocument-only logic.
- v1.12-yf keeps filing-date-only NAV dating as REVIEW_ONLY, excluded from structural stats.
- data_fetch_notes: all price fetches OK
