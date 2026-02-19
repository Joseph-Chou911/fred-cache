# 0050 BB(60,2) + forward_mdd(20D) Report

- report_generated_at_utc: `2026-02-19T02:33:21Z`
- data_source: `yfinance_yahoo_or_twse_fallback`
- ticker: `0050.TW`
- last_date: `2026-02-11`
- bb_window,k: `60`, `2.0`
- forward_window_days: `20`
- price_calc: `adjclose`

## 快速摘要（非預測，僅狀態）
- state: **EXTREME_UPPER_BAND**; bb_z=2.054; pos_in_band=1.014; dist_to_lower=27.60%; dist_to_upper=-0.37%
- forward_mdd(20D) distribution (n=4172): p50=-0.0185; p10=-0.0702; p05=-0.0952; min=-0.7628

## Latest Snapshot

| item | value |
|---|---:|
| close | 77.2000 |
| adjclose | 77.2000 |
| price_used | 77.2000 |
| bb_ma | 66.4043 |
| bb_sd | 5.2552 |
| bb_upper | 76.9148 |
| bb_lower | 55.8939 |
| bb_z | 2.0543 |
| pos_in_band | 1.0136 |
| dist_to_lower | 27.60% |
| dist_to_upper | -0.37% |

## forward_mdd Distribution

- definition: `min(price[t+1..t+20]/price[t]-1), level-price based`

| quantile | value |
|---|---:|
| p50 | -0.0185 |
| p25 | -0.0408 |
| p10 | -0.0702 |
| p05 | -0.0952 |
| min | -0.7628 |

## Recent Raw Prices (tail)

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

- FWD_MDD_OUTLIER_MIN: forward_mdd min=-0.7628 < threshold(-0.4); audit min_entry_date.

## Caveats
- BB 與 forward_mdd 是描述性統計，不是方向預測。
- Yahoo Finance 在 CI 可能被限流；若 fallback 到 TWSE，adjclose=close 並會在 dq flags 留痕。

