# 0050 BB(60,2) + forward_mdd(20D) Report

- report_generated_at_utc: `2026-02-19T03:15:55Z`
- build_script_fingerprint: `build_tw0050_bb_report@2026-02-19.v2`
- stats_path: `tw0050_bb_cache/stats_latest.json`
- stats_has_min_audit_fields: `true`
- data_source: `yfinance_yahoo_or_twse_fallback`
- ticker: `0050.TW`
- last_date: `2026-02-11`
- bb_window,k: `60`, `2.0`
- forward_window_days: `20`
- price_calc: `adjclose`

## 快速摘要（非預測，僅狀態）
- state: **EXTREME_UPPER_BAND**; bb_z=2.0050; pos_in_band=1.0013; dist_to_lower=26.18%; dist_to_upper=-0.03%
- forward_mdd(20D) distribution (n=113): p50=-0.0064; p10=-0.0533; p05=-0.0626; min=-0.0803 (min_window: 2025-10-31->2025-11-24; 64.7500->59.5500)

## Latest Snapshot

| item | value |
|---|---:|
| close | 77.2000 |
| adjclose | 77.2000 |
| price_used | 77.2000 |
| bb_ma | 67.0833 |
| bb_sd | 5.0457 |
| bb_upper | 77.1747 |
| bb_lower | 56.9920 |
| bb_z | 2.0050 |
| pos_in_band | 1.0013 |
| dist_to_lower | 26.18% |
| dist_to_upper | -0.03% |

## forward_mdd Distribution

- definition: `min(price[t+1..t+20]/price[t]-1), level-price based`

| quantile | value |
|---|---:|
| p50 | -0.0064 |
| p25 | -0.0267 |
| p10 | -0.0533 |
| p05 | -0.0626 |
| min | -0.0803 |

### forward_mdd Min Audit Trail

| item | value |
|---|---:|
| min_entry_date | 2025-10-31 |
| min_entry_price | 64.7500 |
| min_future_date | 2025-11-24 |
| min_future_price | 59.5500 |

## Recent Raw Prices (tail 15)

| date | close | adjclose | volume |
|---|---:|---:|---:|
| 2026-01-22 | 71.8000 | 71.8000 | 96360058 |
| 2026-01-23 | 72.2500 | 72.2500 | 68701320 |
| 2026-01-26 | 72.2500 | 72.2500 | 84082813 |
| 2026-01-27 | 73.0500 | 73.0500 | 70421120 |
| 2026-01-28 | 74.2000 | 74.2000 | 87294077 |
| 2026-01-29 | 73.7500 | 73.7500 | 111905919 |
| 2026-01-30 | 72.6000 | 72.6000 | 159055585 |
| 2026-02-02 | 71.5000 | 71.5000 | 211262670 |
| 2026-02-03 | 72.9500 | 72.9500 | 70926930 |
| 2026-02-04 | 72.9000 | 72.9000 | 56597222 |
| 2026-02-05 | 72.0000 | 72.0000 | 95746290 |
| 2026-02-06 | 71.9000 | 71.9000 | 102980565 |
| 2026-02-09 | 73.9500 | 73.9500 | 118533745 |
| 2026-02-10 | 75.5000 | 75.5000 | 98559015 |
| 2026-02-11 | 77.2000 | 77.2000 | 114028587 |

## Data Quality Flags

- YFINANCE_ERROR: yfinance fetch failed: AttributeError: 'tuple' object has no attribute 'lower'
- DATA_SOURCE_TWSE_FALLBACK: Used TWSE fallback (recent-only, months_back=6).

## Caveats
- BB 與 forward_mdd 是描述性統計，不是方向預測。
- Yahoo Finance 在 CI 可能被限流；若 fallback 到 TWSE，adjclose=close 並會在 dq flags 留痕。
