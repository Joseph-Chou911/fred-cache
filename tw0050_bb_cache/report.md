# 0050 BB(60,2) + forward_mdd Report

- report_generated_at_utc: `2026-02-20T17:11:22Z`
- build_script_fingerprint: `build_tw0050_bb_report@2026-02-21.v14`
- stats_path: `tw0050_bb_cache/stats_latest.json`
- data_source: `yfinance_yahoo_or_twse_fallback`
- ticker: `0050.TW`
- last_date: `2026-02-11`
- bb_window,k: `60`, `2.0`
- forward_window_days: `20`
- forward_window_days_short: `10`
- forward_mode_primary: `clean`
- price_calc: `adjclose`
- chip_overlay_path: `tw0050_bb_cache/chip_overlay.json`
- pledge_block_in_stats: `true`
- pledge_version: `pledge_guidance_v1`
- pledge_scope: `compute_only_no_margin_no_chip`

## 快速摘要（非預測，僅狀態）
- state: **EXTREME_UPPER_BAND**; bb_z=2.0543; pos=1.0000 (raw=1.0136); bw_geo=37.61%; bw_std=31.66%
- dist_to_lower=27.60%; dist_to_upper=-0.37%; above_upper=0.37%; below_lower=0.00%; DQ=PRICE_SERIES_BREAK_DETECTED, FWD_MDD_CLEAN_APPLIED, RAW_OUTLIER_EXCLUDED_BY_CLEAN; FWD_OUTLIER=20D
- forward_mdd_clean_20D distribution (n=4152): p50=-0.0183; p10=-0.0687; p05=-0.0928; min=-0.2557 (min_window: 2020-02-19->2020-03-19; 19.4179->14.4528) [DQ:RAW_OUTLIER_EXCLUDED_BY_CLEAN] [DQ:FWD_MDD_OUTLIER_MIN_RAW_20D]
- forward_mdd_clean_10D distribution (n=4172): p50=-0.0114; p10=-0.0480; p05=-0.0631; min=-0.2400 (min_window: 2020-03-05->2020-03-19; 19.0173->14.4528) [DQ:RAW_OUTLIER_EXCLUDED_BY_CLEAN]
- trend_filter(MA200,slope20D,thr=0.50%): price_vs_ma=37.69%; slope=6.13% => **TREND_UP**
- vol_filter(RV20,ATR14): rv_ann=20.7%; atr=1.2304 (1.59%)
- regime(relative_pctl): **RISK_OFF_OR_DEFENSIVE**; allowed=false; rv20_pctl=79.84
- margin(5D,thr=100.00億): TOTAL -197.70 億 => **DELEVERAGING**; TWSE -160.00 / TPEX -37.70; margin_date=2026-02-11, price_last_date=2026-02-11 (ALIGNED); data_date=2026-02-11
- chip_overlay(T86+TWT72U,5D): total3_5D=-8,882,867; foreign=-14,398,187; trust=17,326,000; dealer=-11,810,680; borrow_shares=135,405,000 (Δ1D=-9,446,000); borrow_mv(億)=104.5 (Δ1D=-4.8); asof=20260211; price_last_date=2026-02-11 (ALIGNED)

## Deterministic Action (report-only; non-predictive)

- policy: deterministic rules on existing stats fields only (no forecast)

| item | value |
|---|---:|
| last_date | 2026-02-11 |
| price_used | 77.20 |
| bb_state | EXTREME_UPPER_BAND |
| bb_z | 2.0543 |
| trend_state | TREND_UP |
| regime_tag | **RISK_OFF_OR_DEFENSIVE** |
| regime_allowed | false |
| rv20_percentile | 79.84 |
| rv_pctl_max | 60.00 |
| dq_core | PRICE_SERIES_BREAK_DETECTED, FWD_MDD_CLEAN_APPLIED, RAW_OUTLIER_EXCLUDED_BY_CLEAN |
| margin_note | margin(aligned): total_state=DELEVERAGING, total_sum=-197.7 |
| pledge_block_in_stats | true |
| pledge_version | pledge_guidance_v1 |
| pledge_scope | compute_only_no_margin_no_chip |
| pledge_source | stats |
| pledge_overlay_applied | false |

| item | value |
|---|---:|
| action_bucket_renderer | **HOLD_DEFENSIVE_ONLY** |
| pledge_policy_renderer | **DISALLOW** |
| pledge_veto_reasons_renderer | regime gate closed; action_bucket=HOLD_DEFENSIVE_ONLY; market deleveraging (margin 5D) |
| action_bucket_stats | VETO |
| pledge_policy_stats | DISALLOW |
| pledge_veto_reasons_stats | regime_gate_closed; no_chase_state:EXTREME_UPPER_BAND; no_chase_z>= 1.50 |
| pledge_policy(final) | **DISALLOW** |
| pledge_veto_reasons(final) | stats:regime_gate_closed; stats:no_chase_state:EXTREME_UPPER_BAND; stats:no_chase_z>= 1.50 |
| accumulate_z_threshold | -1.5000 |
| no_chase_z_threshold | 1.5000 |
| pledge_mismatch(stats_vs_renderer) | false |

### decision_path (renderer)
- regime.allowed=false => gate_closed

### tranche_levels (reference; unconditional)

| level | drawdown | price_level |
|---|---:|---:|
| 10D_p10_uncond | -4.80% | 73.50 |
| 10D_p05_uncond | -6.31% | 72.33 |
| 20D_p10_uncond | -6.87% | 71.90 |
| 20D_p05_uncond | -9.28% | 70.04 |

- source: stats (price_anchor=77.20)

### Pledge Guidance v2 (report-only; sizing proposal)

- Purpose: convert binary gate into deterministic size_factor (0..1) using rv20_percentile bands.
- Note: v2 is NOT gated by regime.allowed; it uses rv20_percentile directly and remains conservative under DQ/margin stress.

| item | value |
|---|---:|
| v2_zone | **NO_CHASE** |
| rv20_percentile | 79.84 |
| v2_policy | **DISALLOW** |
| size_factor(0..1) | 0.0000 |
| cooldown_sessions_hint | 0 |
| v2_reasons | zone=NO_CHASE (require ACCUMULATE_ZONE) |

#### v2_zone_path (independent of regime.allowed)
- no_chase: state_has_UPPER=true or bb_z>=1.5

#### v2_tranche_plan (reference-only; scaled by size_factor)

- no tranche plan (size_factor<=0 or levels missing)

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
| pos_in_band (clipped) | 1.0000 |
| pos_in_band_raw (unclipped) | 1.0136 |
| dist_to_lower | 27.60% |
| dist_to_upper | -0.37% |
| above_upper_pct | 0.37% |
| below_lower_pct | 0.00% |
| band_width_geo_pct (upper/lower-1) | 37.61% |
| band_width_std_pct ((upper-lower)/ma) | 31.66% |

## Trend & Vol Filters

| item | value |
|---|---:|
| trend_ma_days | 200 |
| trend_ma_last | 56.0683 |
| trend_slope_days | 20 |
| trend_slope_pct | 6.13% |
| price_vs_trend_ma_pct | 37.69% |
| trend_state | TREND_UP |

| item | value |
|---|---:|
| rv_days | 20 |
| rv_ann(%) | 20.7% |
| rv20_percentile | 79.84 |
| rv_hist_n | 4172 |
| rv_hist_q20(%) | 11.2% |
| rv_hist_q50(%) | 14.8% |
| rv_hist_q80(%) | 20.8% |

| item | value |
|---|---:|
| atr_days | 14 |
| atr | 1.2304 |
| atr_pct | 1.59% |
| tr_mode | OHLC |

## Regime Tag

| item | value |
|---|---:|
| tag | **RISK_OFF_OR_DEFENSIVE** |
| allowed | false |
| trend_state | TREND_UP |
| rv_ann(%) | 20.7% |
| rv20_percentile | 79.84 |
| rv_hist_n | 4172 |
| rv_pctl_max | 60.00 |
| min_samples | 252 |
| pass_trend | true |
| pass_rv_hist | true |
| pass_rv | false |
| bb_state_note | EXTREME_UPPER_BAND |

### Regime Notes
- bb_extreme_upper_band_stretched

## forward_mdd Distribution

### forward_mdd (primary)

- block_used: `forward_mdd_clean_20D`
- definition: `min(price[t+1..t+20]/price[t]-1), level-price based`

| quantile | value |
|---|---:|
| p50 | -0.0183 |
| p25 | -0.0402 |
| p10 | -0.0687 |
| p05 | -0.0928 |
| min | -0.2557 |

#### forward_mdd Min Audit Trail

| item | value |
|---|---:|
| min_entry_date | 2020-02-19 |
| min_entry_price | 19.4179 |
| min_future_date | 2020-03-19 |
| min_future_price | 14.4528 |

### forward_mdd10 (primary)

- block_used: `forward_mdd_clean_10D`
- definition: `min(price[t+1..t+10]/price[t]-1), level-price based`

| quantile | value |
|---|---:|
| p50 | -0.0114 |
| p25 | -0.0271 |
| p10 | -0.0480 |
| p05 | -0.0631 |
| min | -0.2400 |

#### forward_mdd10 Min Audit Trail

| item | value |
|---|---:|
| min_entry_date | 2020-03-05 |
| min_entry_price | 19.0173 |
| min_future_date | 2020-03-19 |
| min_future_price | 14.4528 |

## Chip Overlay（籌碼：TWSE T86 + TWT72U）

- overlay_generated_at_utc: `2026-02-20T17:11:22.479Z`
- stock_no: `0050`
- overlay_window_n: `5` (expect=5)
- date_alignment: overlay_aligned_last_date=`20260211` vs price_last_date=`2026-02-11` => **ALIGNED**

### Borrow Summary（借券：TWT72U）

| item | value |
|---|---:|
| asof_date | 20260211 |
| borrow_shares | 135,405,000 |
| borrow_shares_chg_1d | -9,446,000 |
| borrow_mv_ntd(億) | 104.5 |
| borrow_mv_ntd_chg_1d(億) | -4.8 |

### T86 Aggregate（法人：5D sum）

| item | value |
|---|---:|
| days_used | 20260205, 20260206, 20260209, 20260210, 20260211 |
| foreign_net_shares_sum | -14,398,187 |
| trust_net_shares_sum | 17,326,000 |
| dealer_net_shares_sum | -11,810,680 |
| total3_net_shares_sum | -8,882,867 |

### ETF Units（受益權單位）

| item | value |
|---|---:|
| units_outstanding | 16,191,000,000 |
| units_chg_1d | 44,000,000 |
| dq | (none) |

### Chip Overlay Sources

- T86 template: `https://www.twse.com.tw/fund/T86?response=json&date={ymd}&selectType=ALLBUT0999`
- TWT72U template: `https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={ymd}&selectType=SLBNLB`

## Margin Overlay（融資）

- overlay_generated_at_utc: `2026-02-20T15:08:40Z`
- data_date: `2026-02-11`
- params: window_n=5, threshold_yi=100.00
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

- PRICE_SERIES_BREAK_DETECTED
- FWD_MDD_CLEAN_APPLIED
- FWD_MDD_OUTLIER_MIN_RAW_20D
- RAW_OUTLIER_EXCLUDED_BY_CLEAN

### DQ Notes

- note: Detected 1 break(s) by ratio thresholds; sample: 2014-01-02(r=0.249); hi=1.8, lo=0.555556.
- note: Computed forward_mdd_clean by excluding windows impacted by detected breaks (no price adjustment).
- note: forward_mdd_raw_20D min=-0.7628 < threshold(-0.4); see raw min_audit_trail.
- note: Primary forward_mdd uses CLEAN; raw outlier windows excluded by break mask.

## Caveats
- BB 與 forward_mdd 是描述性統計，不是方向預測。
- Deterministic Action 是規則輸出（report-only），不代表可獲利保證。
- tranche_levels 優先使用 stats 內 pledge.unconditional_tranche_levels.levels；若不存在才由 renderer 用分位數重算。
- dist_to_upper/lower 可能為負值（代表超出通道）；報表額外提供 above_upper / below_lower 以避免符號誤讀。
- Yahoo Finance 在 CI 可能被限流；若 fallback 到 TWSE，為未還原價格，forward_mdd 可能被企業行動污染，DQ 會標示。
- 融資 overlay 屬於市場整體槓桿 proxy；日期不對齊時 overlay 會標示 MISALIGNED。
- Pledge Guidance v2 為報告層 sizing 提案：不改 stats，不構成投資建議。
