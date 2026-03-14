# Private Credit Monitor Report

## Summary
- generated_at_utc: `2026-03-14T07:23:54Z`
- script: `build_private_credit_monitor.py`
- script_version: `v1.6`
- out_dir: `private_credit_cache`
- proxy_signal: **WATCH**
- structural_signal: **NONE**
- combined_signal: **WATCH**
- signal_basis: `PROXY_ONLY`
- overall_confidence: `PARTIAL`
- reasons: `proxy:bdc_basket_median_ret5<=-4 AND below_ma20_share>=80%`
- tags: `proxy:MARKET_PROXY_WEAK`

## 1) BDC Market Proxy
- coverage: `5`
- median_ret1_pct: `-1.162147`
- median_ret5_pct: `-4.644955`
- median_z60: `-1.819365`
- median_drawdown_20d_pct: `-8.457201`
- extreme_z_count: `2`
- extreme_z_share: `40.0`
- ret5_le_minus5_count: `2`
- ret5_le_minus5_share: `40.0`
- below_ma20_count: `5`
- below_ma20_share: `100.0`

| ticker | class | close | data_date | ret1% | ret5% | z60 | p60 | p252 | dd20% | px_vs_ma20% | source | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ARCC | BDC | 17.860000 | 2026-03-13 | -1.162147 | -4.644955 | -2.447509 | 1.666667 | 0.396825 | -8.457201 | -5.553841 | https://stooq.com/q/d/l/?s=arcc.us&d1=20240722&d2=20260314&i=d | OK |
| BXSL | BDC | 23.650000 | 2026-03-13 | -0.253058 | -0.713686 | -1.494594 | 3.333333 | 0.793651 | -4.056795 | -1.765317 | https://stooq.com/q/d/l/?s=bxsl.us&d1=20240722&d2=20260314&i=d | OK |
| FSK | BDC | 10.090000 | 2026-03-13 | -1.464844 | -5.612722 | -2.230994 | 1.666667 | 0.396825 | -24.813711 | -13.771739 | https://stooq.com/q/d/l/?s=fsk.us&d1=20240722&d2=20260314&i=d | OK |
| OBDC | BDC | 10.950000 | 2026-03-13 | -0.363967 | -4.533566 | -1.819365 | 3.333333 | 0.793651 | -8.060453 | -4.345927 | https://stooq.com/q/d/l/?s=obdc.us&d1=20240722&d2=20260314&i=d | OK |
| PSEC | BDC | 2.560000 | 2026-03-13 | -3.396226 | -6.055046 | -1.190850 | 18.333333 | 5.158730 | -16.065574 | -8.105392 | https://stooq.com/q/d/l/?s=psec.us&d1=20240722&d2=20260314&i=d | OK |
| BIZD | ETF_PROXY | 12.480000 | 2026-03-13 | -0.239808 | -2.727981 | -2.010963 | 1.666667 | 0.396825 | -7.142857 | -4.029529 | https://stooq.com/q/d/l/?s=bizd.us&d1=20240722&d2=20260314&i=d | OK |

## 2) NAV Overlay (manual + auto SEC, optional)
- path: `private_credit_cache/inputs/manual_nav.json`
- as_of_date: `YYYY-MM-DD`
- confidence: `PARTIAL`
- raw_row_count: `1`
- template_excluded_count: `1`
- manual_valid_count: `0`
- auto_enabled: `True`
- auto_source: `sec_filings_regex_v3`
- auto_attempted_count: `5`
- auto_found_count: `5`
- manual_override_tickers: `[]`
- coverage_total: `2`
- coverage_fresh: `2`
- median_discount_pct_fresh: `-18.243683`
- median_discount_pct_all: `-18.243683`

| ticker | source_kind | extraction_method | used_in_stats | dq_status | review_flag | match_score | matched_pattern | nav | nav_date | market_close | market_date | premium_discount_pct | nav_age_days | fresh_for_rule | source | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ARCC | auto_sec | implied_from_price_and_rel | True | OK | NONE | 9.900000 | closing_price_discount_to_nav | 19.940653 | 2026-02-04 | 17.860000 | 2026-03-13 | -10.434227 | 37 | True | https://www.sec.gov/Archives/edgar/data/1287750/000128775026000006/arcc-20251231.htm | auto_sec:10-K:2026-02-04:candidate_rank=1 |
| OBDC | auto_sec | implied_from_price_and_rel | True | OK | NONE | 9.900000 | closing_price_discount_to_nav | 14.807931 | 2026-02-18 | 10.950000 | 2026-03-13 | -26.053140 | 23 | True | https://www.sec.gov/Archives/edgar/data/1655888/000165588826000010/obdc-20251231.htm | auto_sec:10-K:2026-02-18:candidate_rank=1 |
| ARCC | manual | manual | False | MANUAL_INVALID | NONE | NA | NA | 0.000000 | NA | 17.860000 | 2026-03-13 | NA | NA | False | https://example.com/investor-relations | Reported NAV per share |
| BXSL | auto_sec | direct | False | REVIEW_SNIPPET_TERMS | SUSPICIOUS_SNIPPET_TERMS | 5.400000 | strict_nav_with_dollar | 25.000000 | 2026-02-25 | 23.650000 | 2026-03-13 | -5.400000 | 16 | True | https://www.sec.gov/Archives/edgar/data/1736035/000173603526000004/bxsl-20251231.htm | auto_sec:10-K:2026-02-25:candidate_rank=1 |
| FSK | auto_sec | direct | False | EXCLUDED_PREMIUM_TOO_HIGH | PREMIUM_GT_25 | 3.100000 | nav_value_after_phrase | 1.000000 | 2026-02-25 | 10.090000 | 2026-03-13 | 909.000000 | 16 | True | https://www.sec.gov/Archives/edgar/data/1422183/000162828026011734/fsk-20251231.htm | auto_sec:10-K:2026-02-25:candidate_rank=1 |
| PSEC | auto_sec | direct | False | REVIEW_DISCOUNT_DEEP | LOW_MATCH_SCORE_LT_3.0|DISCOUNT_LE_-45|PERCENT_NEAR_MATCH|SUSPICIOUS_SNIPPET_TERMS | 1.500000 | nav_value_after_phrase | 5.500000 | 2026-02-09 | 2.560000 | 2026-03-13 | -53.454545 | 32 | True | https://www.sec.gov/Archives/edgar/data/1287032/000128703226000045/psec-20251231.htm | auto_sec:10-Q:2026-02-09:candidate_rank=1 |

### NAV auto match snippets
- ARCC | used_in_stats=True | dq_status=OK | score=9.9 | pattern=closing_price_discount_to_nav | method=implied_from_price_and_rel
  - snippet: `ue, divided by net asset value (in each case, as of the applicable quarter). (3) Represents the dividend or distribution declared in the relevant quarter. On January 29, 2026, the last reported closing sales price of our common stock on The NASDAQ Global Select Market was $20.16 per share, which represented a premium o...`
  - implied_from: price=20.16 | rel=premium | pct=1.1
- OBDC | used_in_stats=True | dq_status=OK | score=9.9 | pattern=closing_price_discount_to_nav | method=implied_from_price_and_rel
  - snippet: `re. See “ ITEM 1A. RISK FACTORS — Risks Related to an Investment in Our Common Stock —The market value of our common stock may fluctuate significantly .” On February 11, 2026, the last reported closing sales price of our common stock on the NYSE was $11.95 per share, which represented a discount of approximately 19.3% ...`
  - implied_from: price=11.95 | rel=discount | pct=19.3
- BXSL | used_in_stats=False | dq_status=REVIEW_SNIPPET_TERMS | score=5.4 | pattern=strict_nav_with_dollar | method=direct
  - snippet: `per share (or such lesser discount to the current market price per share that still exceeded the most recently computed NAV per share). For example, if the most recently computed NAV per share is $25.00 and the market price on the payment date of a cash dividend is $24.00 per share, the Company will issue shares at $24...`
- FSK | used_in_stats=False | dq_status=EXCLUDED_PREMIUM_TOO_HIGH | score=3.1 | pattern=nav_value_after_phrase | method=direct
  - snippet: `Closing Sales Price Premium / (Discount) of High Sales Price to NAV (2) Premium / (Discount) of Low Sales Price to NAV (2) For the Three Months Ended (unless otherwise indicated) NAV per Share (1) High Low Fiscal Year Ending December 31, 2026 First Quarter of 2026 (through February 20, 2026) N/A* $ 14.93 $ 12.75 N/A* N...`
- PSEC | used_in_stats=False | dq_status=REVIEW_DISCOUNT_DEEP | score=1.5 | pattern=nav_value_after_phrase | method=direct
  - snippet: `aintain any stockholder approval that may be required under the 1940 Act to permit us to sell our common stock below net asset value if the 5-day VWAP represents a discount to our net asset value per share of common stock. For the 5.50 % Preferred Stock and 6.50 % Preferred Stock, “IOC Settlement Amount” means (A) the ...`

### NAV auto fetch notes
- ARCC:OK:10-K:2026-02-04:score=9.9:dq=OK:method=implied_from_price_and_rel
- BXSL:WARN:doc_fetch:8-K:HTTPError:503 Server Error: Service Unavailable for url: https://www.sec.gov/Archives/edgar/data/1736035/00012
- BXSL:WARN:doc_fetch:8-K:HTTPError:503 Server Error: Service Unavailable for url: https://www.sec.gov/Archives/edgar/data/1736035/00012
- BXSL:WARN:doc_fetch:8-K:HTTPError:503 Server Error: Service Unavailable for url: https://www.sec.gov/Archives/edgar/data/1736035/00012
- BXSL:REVIEW_ONLY:10-K:2026-02-25:score=5.4:dq=REVIEW_SNIPPET_TERMS:method=direct
- OBDC:OK:10-K:2026-02-18:score=9.9:dq=OK:method=implied_from_price_and_rel
- FSK:WARN:doc_fetch:8-K:HTTPError:503 Server Error: Service Unavailable for url: https://www.sec.gov/Archives/edgar/data/1422183/00011
- FSK:WARN:doc_fetch:8-K:HTTPError:503 Server Error: Service Unavailable for url: https://www.sec.gov/Archives/edgar/data/1422183/00011
- FSK:REVIEW_ONLY:10-K:2026-02-25:score=3.1:dq=EXCLUDED_PREMIUM_TOO_HIGH:method=direct
- PSEC:REVIEW_ONLY:10-Q:2026-02-09:score=1.5:dq=REVIEW_DISCOUNT_DEEP:method=direct

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
- nav_confidence: `PARTIAL`
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
- data_fetch_notes: all price fetches OK
