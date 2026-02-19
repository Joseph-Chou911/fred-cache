# 0050 BB(60,2) + forward_mdd(20D) Report

- report_generated_at_utc: `2026-02-19T08:13:54Z`
- build_script_fingerprint: `build_tw0050_bb_report@2026-02-19.v6`
- stats_path: `tw0050_bb_cache/stats_latest.json`
- stats_has_min_audit_fields: `true`
- data_source: `yfinance_yahoo_or_twse_fallback`
- ticker: `0050.TW`
- last_date: `2026-02-11`
- bb_window,k: `60`, `2.0`
- forward_window_days: `20`
- price_calc: `adjclose`
- chip_overlay_path: `tw0050_bb_cache/chip_overlay.json`

## 快速摘要（非預測，僅狀態）
- state: **EXTREME_UPPER_BAND**; bb_z=2.0543; pos_in_band=1.0136; dist_to_lower=38.12%; dist_to_upper=0.37%
- forward_mdd(20D) distribution (n=4151): p50=-0.0183; p10=-0.0687; p05=-0.0928; min=-0.2557 (min_window: 2020-02-19->2020-03-19; 19.4179->14.4528) [DQ:RAW_OUTLIER_EXCLUDED]
- trend_filter(MA200,slope20D,thr=0.50%): price_vs_ma=37.69%; slope=6.13% => **TREND_UP**
- vol_filter(RV20,ATR14): rv_ann=20.7%; atr=1.2304 (1.59%)
- regime(relative_pctl): **RISK_OFF_OR_DEFENSIVE**; allowed=false; rv20_pctl=79.84
- margin(5D,thr=100.00億): TOTAL -197.70 億 => **DELEVERAGING**; TWSE -160.00 / TPEX -37.70; margin_date=2026-02-11, price_last_date=2026-02-11 (ALIGNED); data_date=2026-02-11
- chip_overlay(T86+TWT72U,5D): total3_5D=-8,882,867; foreign=-14,398,187; trust=17,326,000; dealer=-11,810,680; borrow_shares=135,405,000 (Δ1D=-9,446,000); borrow_mv(億)=104.5 (Δ1D=-4.8); asof=20260211; price_last_date=2026-02-11 (ALIGNED)

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

## Chip Overlay（籌碼：TWSE T86 + TWT72U）

- overlay_generated_at_utc: `2026-02-19T08:13:54.501028Z`
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
| units_outstanding | N/A |
| units_chg_1d | N/A |
| dq | ETF_UNITS_ENDPOINT_NOT_IMPLEMENTED |

### Chip Overlay Sources

- T86 template: `https://www.twse.com.tw/fund/T86?response=json&date={ymd}&selectType=ALLBUT0999`
- TWT72U template: `https://www.twse.com.tw/exchangeReport/TWT72U?response=json&date={ymd}&selectType=SLBNLB`

### Chip Overlay DQ

- ETF_UNITS_ENDPOINT_NOT_IMPLEMENTED

## Margin Overlay（融資）

- overlay_generated_at_utc: `2026-02-18T15:13:18Z`
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

- PRICE_SERIES_BREAK_DETECTED: Detected 1 break(s) by ratio thresholds; sample: 2014-01-02(r=0.249); hi=1.8, lo=0.555556.
- FWD_MDD_CLEAN_APPLIED: Computed forward_mdd_clean by excluding windows impacted by detected breaks (no price adjustment).
- FWD_MDD_OUTLIER_MIN_RAW: forward_mdd_raw min=-0.7628 < threshold(-0.4); see raw min_audit_trail.
- RAW_OUTLIER_EXCLUDED: Primary forward_mdd uses CLEAN; raw outlier windows excluded by break mask.

### Chip Overlay DQ (extra)
- CHIP_OVERLAY:ETF_UNITS_ENDPOINT_NOT_IMPLEMENTED

## Caveats
- BB 與 forward_mdd 是描述性統計，不是方向預測。
- Yahoo Finance 在 CI 可能被限流；若 fallback 到 TWSE，adjclose=close 並會在 dq flags 留痕。
- Trend/Vol/ATR 是濾網與風險量級提示，不是進出場保證；若資料不足會以 DQ 明示。
- 融資 overlay 屬於市場整體槓桿/風險偏好 proxy，不等同 0050 自身籌碼；若日期不對齊應降低解讀權重。
- Chip overlay（T86/TWT72U）是籌碼/借券的描述資訊；ETF 申贖與避險行為可能影響解讀，建議視為輔助註記而非單一交易信號。
