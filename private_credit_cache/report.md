# Private Credit Monitor Report

## Summary
- generated_at_utc: `2026-03-14T07:09:52Z`
- script: `build_private_credit_monitor.py`
- script_version: `v1.5`
- out_dir: `private_credit_cache`
- proxy_signal: **WATCH**
- structural_signal: **ALERT**
- combined_signal: **ALERT**
- signal_basis: `MIXED`
- overall_confidence: `PARTIAL`
- reasons: `proxy:bdc_basket_median_ret5<=-4 AND below_ma20_share>=80%; structural:fresh_nav_median_discount<=-20 with coverage>=3`
- tags: `proxy:MARKET_PROXY_WEAK,structural:NAV_DISCOUNT_STRESS`

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
- confidence: `OK`
- raw_row_count: `1`
- template_excluded_count: `1`
- manual_valid_count: `0`
- auto_enabled: `True`
- auto_source: `sec_filings_regex_v2`
- auto_attempted_count: `5`
- auto_found_count: `5`
- manual_override_tickers: `[]`
- coverage_total: `4`
- coverage_fresh: `4`
- median_discount_pct_fresh: `-37.560215`
- median_discount_pct_all: `-37.560215`

| ticker | source_kind | used_in_stats | dq_status | review_flag | match_score | matched_pattern | nav | nav_date | market_close | market_date | premium_discount_pct | nav_age_days | fresh_for_rule | source | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ARCC | auto_sec | True | OK | NONE | 7.000000 | net_asset_value_per_share | 31.000000 | 2026-02-04 | 17.860000 | 2026-03-13 | -42.387097 | 37 | True | https://www.sec.gov/Archives/edgar/data/1287750/000128775026000006/arcc-20251231.htm | auto_sec:10-K:2026-02-04:candidate_rank=1 |
| BXSL | auto_sec | True | OK | NONE | 6.400000 | net_asset_value_per_share | 31.000000 | 2026-02-25 | 23.650000 | 2026-03-13 | -23.709677 | 16 | True | https://www.sec.gov/Archives/edgar/data/1736035/000173603526000004/bxsl-20251231.htm | auto_sec:10-K:2026-02-25:candidate_rank=1 |
| FSK | auto_sec | True | OK | NONE | 6.400000 | net_asset_value_per_share | 15.000000 | 2026-02-25 | 10.090000 | 2026-03-13 | -32.733333 | 16 | True | https://www.sec.gov/Archives/edgar/data/1422183/000162828026011734/fsk-20251231.htm | auto_sec:10-K:2026-02-25:candidate_rank=1 |
| OBDC | auto_sec | True | REVIEW_DISCOUNT_DEEP | DISCOUNT_LE_-45 | 6.700000 | net_asset_value_per_share | 31.000000 | 2026-02-18 | 10.950000 | 2026-03-13 | -64.677419 | 23 | True | https://www.sec.gov/Archives/edgar/data/1655888/000165588826000010/obdc-20251231.htm | auto_sec:10-K:2026-02-18:candidate_rank=1 |
| ARCC | manual | False | MANUAL_INVALID | NONE | NA | NA | 0.000000 | NA | 17.860000 | 2026-03-13 | NA | NA | False | https://example.com/investor-relations | Reported NAV per share |
| PSEC | auto_sec | False | EXCLUDED_LOW_MATCH_SCORE | LOW_MATCH_SCORE_LT_3.0 | 2.900000 | net_asset_value_per_share | 5.500000 | 2026-02-09 | 2.560000 | 2026-03-13 | -53.454545 | 32 | True | https://www.sec.gov/Archives/edgar/data/1287032/000128703226000045/psec-20251231.htm | auto_sec:10-Q:2026-02-09:candidate_rank=1 |

### NAV auto match snippets
- ARCC | used_in_stats=True | dq_status=OK | score=7.0 | pattern=net_asset_value_per_share
  - snippet: `2026, the last reported closing sales price of our common stock on The NASDAQ Global Select Market was $20.16 per share, which represented a premium of approximately 1.10% to the net asset value per share reported by us as of December 31, 2025. HOLDERS As of January 29, 2026, there were 910 holders of record of our com...`
- BXSL | used_in_stats=True | dq_status=OK | score=6.4 | pattern=net_asset_value_per_share
  - snippet: `e 16a-1(a)(2) under the Exchange Act. (2) Dollar ranges were determined using the number of shares that are beneficially owned as of February 18, 2026, multiplied by the Company’s net asset value per share as of December 31, 2025. (3) The “Fund Complex” consists of the Company, BCRED, the Blackstone Credit & Insurance ...`
- FSK | used_in_stats=True | dq_status=OK | score=6.4 | pattern=net_asset_value_per_share
  - snippet: `and our stockholders approve such sale. At the 2025 annual stockholders meeting, our stockholders approved the sale of shares of our common stock at a price below the then-current net asset value per share, subject to certain conditions, during the period beginning on August 15, 2025 and expiring on August 15, 2026. We...`
- OBDC | used_in_stats=True | dq_status=REVIEW_DISCOUNT_DEEP | score=6.7 | pattern=net_asset_value_per_share
  - snippet: `icantly .” On February 11, 2026, the last reported closing sales price of our common stock on the NYSE was $11.95 per share, which represented a discount of approximately 19.3% to net asset value per share reported by us as of December 31, 2025. Holders As of February 11, 2026, there were approximately 25 holders of re...`
- PSEC | used_in_stats=False | dq_status=EXCLUDED_LOW_MATCH_SCORE | score=2.9 | pattern=net_asset_value_per_share
  - snippet: `aintain any stockholder approval that may be required under the 1940 Act to permit us to sell our common stock below net asset value if the 5-day VWAP represents a discount to our net asset value per share of common stock. For the 5.50 % Preferred Stock and 6.50 % Preferred Stock, “IOC Settlement Amount” means (A) the ...`

### NAV auto fetch notes
- ARCC:WARN:doc_fetch:8-K:HTTPError:503 Server Error: Service Unavailable for url: https://www.sec.gov/Archives/edgar/data/1287750/00012
- ARCC:OK:10-K:2026-02-04:score=7.0:dq=OK
- BXSL:WARN:doc_fetch:8-K:HTTPError:503 Server Error: Service Unavailable for url: https://www.sec.gov/Archives/edgar/data/1736035/00012
- BXSL:WARN:doc_fetch:8-K:HTTPError:503 Server Error: Service Unavailable for url: https://www.sec.gov/Archives/edgar/data/1736035/00012
- BXSL:OK:10-K:2026-02-25:score=6.4:dq=OK
- OBDC:OK:10-K:2026-02-18:score=6.7:dq=REVIEW_DISCOUNT_DEEP
- FSK:OK:10-K:2026-02-25:score=6.4:dq=OK
- PSEC:WARN:doc_fetch:8-K:HTTPError:503 Server Error: Service Unavailable for url: https://www.sec.gov/Archives/edgar/data/1287032/00012
- PSEC:WARN:doc_fetch:8-K:HTTPError:503 Server Error: Service Unavailable for url: https://www.sec.gov/Archives/edgar/data/1287032/00012
- PSEC:REVIEW_ONLY:10-Q:2026-02-09:score=2.9:dq=EXCLUDED_LOW_MATCH_SCORE

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
- Auto NAV from SEC now records matched snippets, review flags, and excludes suspicious auto rows from structural stats by default.
- data_fetch_notes: all price fetches OK
