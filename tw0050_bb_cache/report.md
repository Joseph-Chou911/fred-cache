# 0050 BB(60,2) + forward_mdd Report

- report_generated_at_utc: `2026-02-20T12:11:37Z`
- build_script_fingerprint: `build_tw0050_bb_report@2026-02-20.v12`
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

## 快速摘要（非預測，僅狀態）
- state: **EXTREME_UPPER_BAND**; bb_z=2.0543; pos=1.0000 (raw=1.0136); bw_geo=37.61%; bw_std=31.66%
- dist_to_lower=27.60%; dist_to_upper=-0.37%; above_upper=0.37%; below_lower=0.00%; DQ=PRICE_SERIES_BREAK_DETECTED; FWD_CLEAN=ON; FWD_MASK=ON; FWD_RAW_OUTLIER=20D
- forward_mdd_clean_20D distribution (n=4151): p50=-0.0183; p10=-0.0687; p05=-0.0928; min=-0.2557 (min_window: 2020-02-19->2020-03-19; 19.4179->14.4528) [DQ:RAW_OUTLIER_EXCLUDED_BY_CLEAN] [DQ:FWD_MDD_OUTLIER_MIN_RAW_20D]
- forward_mdd_clean_10D distribution (n=4171): p50=-0.0114; p10=-0.0480; p05=-0.0631; min=-0.2400 (min_window: 2020-03-05->2020-03-19; 19.0173->14.4528) [DQ:RAW_OUTLIER_EXCLUDED_BY_CLEAN]
- trend_filter(MA200,slope20D,thr=0.50%): price_vs_ma=37.69%; slope=6.13% => **TREND_UP**
- vol_filter(RV20,ATR14): rv_ann=20.7%; atr=1.2304 (1.59%)
- regime(relative_pctl): **RISK_OFF_OR_DEFENSIVE**; allowed=false; rv20_pctl=79.84
- chip_overlay(T86+TWT72U,5D): total3_5D=N/A; foreign=N/A; trust=N/A; dealer=N/A; borrow_shares=N/A (Δ1D=N/A); borrow_mv(億)=N/A (Δ1D=N/A); asof=N/A; price_last_date=2026-02-11 (ALIGNED)

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

- overlay_generated_at_utc: `N/A`
- stock_no: `0050`
- overlay_window_n: `N/A` (expect=N/A)
- date_alignment: overlay_aligned_last_date=`N/A` vs price_last_date=`2026-02-11` => **N/A**

### Borrow Summary（借券：TWT72U）

| item | value |
|---|---:|
| asof_date | N/A |
| borrow_shares | N/A |
| borrow_shares_chg_1d | N/A |
| borrow_mv_ntd(億) | N/A |
| borrow_mv_ntd_chg_1d(億) | N/A |

### T86 Aggregate（法人：5D sum）

| item | value |
|---|---:|
| days_used |  |
| foreign_net_shares_sum | N/A |
| trust_net_shares_sum | N/A |
| dealer_net_shares_sum | N/A |
| total3_net_shares_sum | N/A |

### ETF Units（受益權單位）

| item | value |
|---|---:|
| units_outstanding | N/A |
| units_chg_1d | N/A |
| dq | {'flags': []} |

### Chip Overlay Sources

- T86 template: `https://www.twse.com.tw/fund/T86?response=json&date={ymd}&selectType=ALLBUT0999`
- TWT72U template: `https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={ymd}&selectType=SLBNLB`

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
- note: Clean masks built per-window: clean20 excludes entries whose [t+1..t+20] includes break; clean10 excludes entries whose [t+1..t+10] includes break.
- note: forward_mdd_raw_20D min=-0.7628 < threshold(-0.4); see raw min_audit_trail.
- note: Primary forward_mdd uses CLEAN; raw outlier windows excluded by break mask.

## Caveats
- BB 與 forward_mdd 是描述性統計，不是方向預測。
- pos_in_band 會顯示 clipped 值（0..1）與 raw 值（可超界，用於稽核）。
- dist_to_upper/lower 可能為負值（代表超出通道）；報表已額外提供 above_upper / below_lower 以避免符號誤讀。
- band_width 同時提供兩種定義：geo=(upper/lower-1)、std=(upper-lower)/ma；請勿混用解讀。
- Yahoo Finance 在 CI 可能被限流；若 fallback 到 TWSE，為未還原價格，forward_mdd 可能被除權息/企業行動污染，DQ 會標示。
- Trend/Vol/ATR 是濾網與風險量級提示，不是進出場保證；資料不足會以 DQ 明示。
- 融資 overlay 屬於市場整體槓桿/風險偏好 proxy，不等同 0050 自身籌碼；日期不對齊需降低解讀權重。
- Chip overlay（T86/TWT72U）為籌碼/借券描述；ETF 申贖、避險行為可能影響解讀，建議只做輔助註記。
