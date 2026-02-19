# 0050 BB(60,2) + forward_mdd(20D) Report

- report_generated_at_utc: `2026-02-19T04:24:11Z`
- build_script_fingerprint: `build_tw0050_bb_report@2026-02-19.v3`
- stats_path: `tw0050_bb_cache/stats_latest.json`
- stats_has_min_audit_fields: `true`
- data_source: `yfinance_yahoo_or_twse_fallback`
- ticker: `0050.TW`
- last_date: `2026-02-11`
- bb_window,k: `60`, `2.0`
- forward_window_days: `20`
- price_calc: `adjclose`

## 快速摘要（非預測，僅狀態）
- state: **EXTREME_UPPER_BAND**; bb_z=2.0543; pos_in_band=1.0136; dist_to_lower=38.12%; dist_to_upper=0.37%
- forward_mdd(20D) distribution (n=4151): p50=-0.0183; p10=-0.0687; p05=-0.0928; min=-0.2557 (min_window: 2020-02-19->2020-03-19; 19.4179->14.4528) [DQ:FWD_MDD_OUTLIER_MIN_RAW]
- margin(5D,thr=100.0億): TOTAL -197.7 億 => **DELEVERAGING**; TWSE -160.0 / TPEX -37.7; margin_date=2026-02-11, price_last_date=2026-02-11 (ALIGNED); data_date=2026-02-11

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
| dist_to_lower | 38.12% |
| dist_to_upper | 0.37% |

## forward_mdd Distribution

- definition: `min(price[t+1..t+20]/price[t]-1), level-price based`

| quantile | value |
|---|---:|
| p50 | -0.0183 |
| p25 | -0.0402 |
| p10 | -0.0687 |
| p05 | -0.0928 |
| min | -0.2557 |

### forward_mdd Min Audit Trail

| item | value |
|---|---:|
| min_entry_date | 2020-02-19 |
| min_entry_price | 19.4179 |
| min_future_date | 2020-03-19 |
| min_future_price | 14.4528 |

## Margin Overlay（融資）

- overlay_generated_at_utc: `2026-02-18T15:13:18Z`
- data_date: `2026-02-11`
- params: window_n=5, threshold_yi=100.0
- date_alignment: margin_latest_date=`2026-02-11` vs price_last_date=`2026-02-11` => **ALIGNED**

| scope | latest_date | balance(億) | chg_today(億) | chg_ND_sum(億) | state_ND | rows_used |
|---|---:|---:|---:|---:|---:|---:|
| TWSE | 2026-02-11 | 3,680.5 | -45.4 | -160.0 | DELEVERAGING | 5 |
| TPEX | 2026-02-11 | 1,313.3 | -9.0 | -37.7 | NEUTRAL | 5 |
| TOTAL | 2026-02-11 | 4,993.8 | N/A | -197.7 | DELEVERAGING | N/A |

### Margin Sources

- TWSE source: `HiStock`
- TWSE url: `https://histock.tw/stock/three.aspx?m=mg`
- TPEX source: `HiStock`
- TPEX url: `https://histock.tw/stock/three.aspx?m=mg&no=TWOI`

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

- PRICE_SERIES_BREAK_DETECTED: Detected 1 break(s) by ratio thresholds; sample: 2014-01-02(r=0.249); hi=1.8, lo=0.555556.
- FWD_MDD_CLEAN_APPLIED: Computed forward_mdd_clean by excluding windows impacted by detected breaks (no price adjustment).
- FWD_MDD_OUTLIER_MIN_RAW: forward_mdd_raw min=-0.7628 < threshold(-0.4); see raw min_audit_trail.

## Caveats
- BB 與 forward_mdd 是描述性統計，不是方向預測。
- Yahoo Finance 在 CI 可能被限流；若 fallback 到 TWSE，adjclose=close 並會在 dq flags 留痕。
- 融資 overlay 屬於市場整體槓桿/風險偏好 proxy，不等同 0050 自身籌碼；若日期不對齊應降低解讀權重。
