# 0050 BB(60,2) + forward_mdd Report

- report_generated_at_utc: `2026-02-20T19:11:16Z`
- build_script_fingerprint: `build_tw0050_bb_report@2026-02-21.v15.add_fwd_mdd_conditional_block`
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

## Forward MDD Conditional (by bb_z bucket)

| item | value |
|---|---:|
| scheme | bb_z_5bucket_v1 |
| thresholds.near | 1.5000 |
| thresholds.extreme | 2.0000 |
| forward_mode_primary(meta) | clean |
| current_bb_z | 2.0543 |
| current_bucket_id | **z_ge_2.0** |

### current_bucket quick summary

- 20D (primary, bucket=z_ge_2.0): n=396; p50=-0.0123; p10=-0.0502; p05=-0.0666; min=-0.2130 (min_window 2024-07-11->2024-08-05)
- 10D (primary, bucket=z_ge_2.0): n=406; p50=-0.0082; p10=-0.0316; p05=-0.0499; min=-0.1126 (min_window 2024-07-11->2024-07-26)

### full tables

#### 20D

| mode | bucket_id | bucket_label | n | p50 | p25 | p10 | p05 | min | min_window | min_price(entry→future) |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| primary | z_le_-2.0 | bb_z<=-2.0 | 205 | -0.0329 | -0.0614 | -0.1265 | -0.1902 | -0.2152 | 2020-03-02→2020-03-19 | 18.4165→14.4528 |
| primary | -2.0_to_-1.5 | -2.0<bb_z<=-1.5 | 205 | -0.0214 | -0.0513 | -0.0866 | -0.1137 | -0.2267 | 2020-02-27→2020-03-19 | 18.6905→14.4528 |
| primary | -1.5_to_1.5 | -1.5<bb_z<1.5 | 2,632 | -0.0183 | -0.0406 | -0.0679 | -0.0913 | -0.2557 | 2020-02-19→2020-03-19 | 19.4179→14.4528 |
| primary | 1.5_to_2.0 | 1.5<=bb_z<2.0 | 655 | -0.0168 | -0.0358 | -0.0600 | -0.0735 | -0.1935 | 2024-07-16→2024-08-05 | 47.5311→38.3315 |
| primary | **z_ge_2.0** | bb_z>=2.0 | 396 | -0.0123 | -0.0282 | -0.0502 | -0.0666 | -0.2130 | 2024-07-11→2024-08-05 | 48.7068→38.3315 |
| clean | z_le_-2.0 | bb_z<=-2.0 | 205 | -0.0329 | -0.0614 | -0.1265 | -0.1902 | -0.2152 | 2020-03-02→2020-03-19 | 18.4165→14.4528 |
| clean | -2.0_to_-1.5 | -2.0<bb_z<=-1.5 | 205 | -0.0214 | -0.0513 | -0.0866 | -0.1137 | -0.2267 | 2020-02-27→2020-03-19 | 18.6905→14.4528 |
| clean | -1.5_to_1.5 | -1.5<bb_z<1.5 | 2,632 | -0.0183 | -0.0406 | -0.0679 | -0.0913 | -0.2557 | 2020-02-19→2020-03-19 | 19.4179→14.4528 |
| clean | 1.5_to_2.0 | 1.5<=bb_z<2.0 | 655 | -0.0168 | -0.0358 | -0.0600 | -0.0735 | -0.1935 | 2024-07-16→2024-08-05 | 47.5311→38.3315 |
| clean | **z_ge_2.0** | bb_z>=2.0 | 396 | -0.0123 | -0.0282 | -0.0502 | -0.0666 | -0.2130 | 2024-07-11→2024-08-05 | 48.7068→38.3315 |
| raw | z_le_-2.0 | bb_z<=-2.0 | 205 | -0.0329 | -0.0614 | -0.1265 | -0.1902 | -0.2152 | 2020-03-02→2020-03-19 | 18.4165→14.4528 |
| raw | -2.0_to_-1.5 | -2.0<bb_z<=-1.5 | 205 | -0.0214 | -0.0513 | -0.0866 | -0.1137 | -0.2267 | 2020-02-27→2020-03-19 | 18.6905→14.4528 |
| raw | -1.5_to_1.5 | -1.5<bb_z<1.5 | 2,648 | -0.0186 | -0.0412 | -0.0697 | -0.0933 | -0.7513 | 2013-12-23→2014-01-09 | 36.8707→9.1699 |
| raw | 1.5_to_2.0 | 1.5<=bb_z<2.0 | 657 | -0.0170 | -0.0358 | -0.0608 | -0.0748 | -0.7532 | 2013-12-27→2014-01-09 | 37.1575→9.1699 |
| raw | **z_ge_2.0** | bb_z>=2.0 | 398 | -0.0124 | -0.0288 | -0.0504 | -0.0673 | -0.7628 | 2013-12-30→2014-02-05 | 37.4761→8.8910 |

#### 10D

| mode | bucket_id | bucket_label | n | p50 | p25 | p10 | p05 | min | min_window | min_price(entry→future) |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| primary | z_le_-2.0 | bb_z<=-2.0 | 205 | -0.0222 | -0.0436 | -0.0721 | -0.1124 | -0.2057 | 2020-03-10→2020-03-19 | 18.1951→14.4528 |
| primary | -2.0_to_-1.5 | -2.0<bb_z<=-1.5 | 205 | -0.0181 | -0.0426 | -0.0607 | -0.0785 | -0.2241 | 2020-03-06→2020-03-19 | 18.6273→14.4528 |
| primary | -1.5_to_1.5 | -1.5<bb_z<1.5 | 2,641 | -0.0117 | -0.0272 | -0.0468 | -0.0595 | -0.2400 | 2020-03-05→2020-03-19 | 19.0173→14.4528 |
| primary | 1.5_to_2.0 | 1.5<=bb_z<2.0 | 656 | -0.0095 | -0.0232 | -0.0388 | -0.0567 | -0.1009 | 2009-06-03→2009-06-17 | 29.7584→26.7570 |
| primary | **z_ge_2.0** | bb_z>=2.0 | 406 | -0.0082 | -0.0183 | -0.0316 | -0.0499 | -0.1126 | 2024-07-11→2024-07-26 | 48.7068→43.2210 |
| clean | z_le_-2.0 | bb_z<=-2.0 | 205 | -0.0222 | -0.0436 | -0.0721 | -0.1124 | -0.2057 | 2020-03-10→2020-03-19 | 18.1951→14.4528 |
| clean | -2.0_to_-1.5 | -2.0<bb_z<=-1.5 | 205 | -0.0181 | -0.0426 | -0.0607 | -0.0785 | -0.2241 | 2020-03-06→2020-03-19 | 18.6273→14.4528 |
| clean | -1.5_to_1.5 | -1.5<bb_z<1.5 | 2,641 | -0.0117 | -0.0272 | -0.0468 | -0.0595 | -0.2400 | 2020-03-05→2020-03-19 | 19.0173→14.4528 |
| clean | 1.5_to_2.0 | 1.5<=bb_z<2.0 | 656 | -0.0095 | -0.0232 | -0.0388 | -0.0567 | -0.1009 | 2009-06-03→2009-06-17 | 29.7584→26.7570 |
| clean | **z_ge_2.0** | bb_z>=2.0 | 406 | -0.0082 | -0.0183 | -0.0316 | -0.0499 | -0.1126 | 2024-07-11→2024-07-26 | 48.7068→43.2210 |
| raw | z_le_-2.0 | bb_z<=-2.0 | 205 | -0.0222 | -0.0436 | -0.0721 | -0.1124 | -0.2057 | 2020-03-10→2020-03-19 | 18.1951→14.4528 |
| raw | -2.0_to_-1.5 | -2.0<bb_z<=-1.5 | 205 | -0.0181 | -0.0426 | -0.0607 | -0.0785 | -0.2241 | 2020-03-06→2020-03-19 | 18.6273→14.4528 |
| raw | -1.5_to_1.5 | -1.5<bb_z<1.5 | 2,648 | -0.0117 | -0.0274 | -0.0471 | -0.0600 | -0.7513 | 2013-12-25→2014-01-09 | 36.8707→9.1699 |
| raw | 1.5_to_2.0 | 1.5<=bb_z<2.0 | 657 | -0.0095 | -0.0232 | -0.0391 | -0.0567 | -0.7532 | 2013-12-27→2014-01-09 | 37.1575→9.1699 |
| raw | **z_ge_2.0** | bb_z>=2.0 | 408 | -0.0082 | -0.0184 | -0.0323 | -0.0515 | -0.7553 | 2013-12-30→2014-01-09 | 37.4761→9.1699 |

- note: condition evaluated at entry t using bb_z[t]; stats computed on already-produced forward_mdd arrays (respecting raw/clean masks).

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
| rv_ann | 0.2070 |
| rv_ann_pctl | 79.84 |
| rv_hist_n | 4,172 |
| rv_hist_q20 | 0.1120 |
| rv_hist_q50 | 0.1483 |
| rv_hist_q80 | 0.2080 |

| item | value |
|---|---:|
| atr_days | 14 |
| atr | 1.2304 |
| atr_pct | 1.59% |
| tr_mode | OHLC |

## Data Quality

### dq.flags
- PRICE_SERIES_BREAK_DETECTED
- FWD_MDD_CLEAN_APPLIED
- FWD_MDD_OUTLIER_MIN_RAW_20D
- RAW_OUTLIER_EXCLUDED_BY_CLEAN

### dq.notes
- Detected 1 break(s) by ratio thresholds; sample: 2014-01-02(r=0.249); hi=1.8, lo=0.555556.
- Computed forward_mdd_clean by excluding windows impacted by detected breaks (no price adjustment).
- forward_mdd_raw_20D min=-0.7628 < threshold(-0.4); see raw min_audit_trail.
- Primary forward_mdd uses CLEAN; raw outlier windows excluded by break mask.

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

## Chip Overlay（籌碼：TWSE T86 + TWT72U）

- overlay_generated_at_utc: `2026-02-20T19:11:16.653Z`
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

## Price Tail

- tail_n: 15

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
