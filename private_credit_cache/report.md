# Private Credit Monitor Report

## Summary
- generated_at_utc: `2026-03-14T04:40:54Z`
- script: `build_private_credit_monitor.py`
- script_version: `v1.1`
- out_dir: `private_credit_cache`
- proxy_signal: **WATCH**
- structural_signal: **NONE**
- combined_signal: **WATCH**
- signal_basis: `PROXY_ONLY`
- overall_confidence: `PROXY_ONLY`
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

## 2) NAV Overlay (manual, optional)
- path: `private_credit_cache/inputs/manual_nav.json`
- as_of_date: `YYYY-MM-DD`
- confidence: `TEMPLATE_ONLY`
- raw_row_count: `1`
- template_excluded_count: `1`
- coverage_total: `0`
- coverage_fresh: `0`
- median_discount_pct_fresh: `None`
- median_discount_pct_all: `None`

| ticker | nav | nav_date | market_close | market_date | premium_discount_pct | nav_age_days | fresh_for_rule | valid_for_stats | template_excluded | source | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ARCC | 0.000000 | NA | 17.860000 | 2026-03-13 | NA | NA | False | False | True | https://example.com/investor-relations | Reported NAV per share |

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

| series | signal | value | data_date | reason | tag |
| --- | --- | --- | --- | --- | --- |
| BAMLH0A0HYM2 | NA | 3.170000 | 2026-03-12 | abs(Z60)>=2 | EXTREME_Z |
| HYG_IEF_RATIO | NA | 0.828539 | 2026-03-13 | NA | NA |
| OFR_FSI | NA | -0.925000 | 2026-03-11 | abs(Z60)>=2;abs(Z60)>=2.5;abs(ZΔ60)>=0.75;abs(ret1%1d)>=2 | EXTREME_Z,JUMP_ZD,JUMP_RET |

## 5) Confidence / DQ
- price_confidence: `OK`
- nav_confidence: `TEMPLATE_ONLY`
- event_confidence: `TEMPLATE_ONLY`
- structural_confidence: `PROXY_ONLY`
- overall_confidence: `PROXY_ONLY`
- basket_coverage: `5`

## 6) Notes
- This module is display-only / advisory-only by design.
- HY spread / HYG-IEF / OFR_FSI are NOT recomputed here.
- Manual overlays are expected for event flags and latest NAV values.
- Template / invalid manual rows are excluded from coverage/count/median statistics.
- combined_signal should be interpreted together with signal_basis and structural_confidence.
- data_fetch_notes: all price fetches OK
