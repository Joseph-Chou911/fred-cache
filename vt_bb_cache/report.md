# VT BB Monitor Report (VT + optional USD/TWD)

- report_generated_at_utc: `2026-02-20T03:56:36Z`
- data_date: `2026-02-19`
- price_mode: `adj_close`
- params: `BB(60,2.0) on log(price)`, `forward_mdd(20D)`

## 15秒摘要
- **VT** (2026-02-19 price_usd=146.6800) → **MID_BAND** (z=1.2032, pos=0.8008); dist_to_lower=6.668%; dist_to_upper=1.732%; 20D forward_mdd: p50=-1.637%, p10=-7.279%, min=-31.571% (n=2896, conf=HIGH, conf_decision=OK, min_n_required=200)

## Δ1D（一日變動；以前一個「可計算 BB 的交易日」為基準）
- prev_bb_date: `2026-02-18`
- Δprice_1d: -0.224%
- Δz_1d: -0.0933
- Δpos_1d: -0.0233
- Δband_width_1d: -0.603%
- Δdist_to_upper_1d: 0.106%

## 解讀重點（更詳盡）
- **Band 位置**：pos=0.8008（≥0.80 視為「靠近上緣」閱讀提示；此提示不改 bucket 規則）
- **距離上下軌**：dist_to_upper=1.732%；dist_to_lower=6.668%
- **波動區間寬度（閱讀用）**：band_width≈9.000%（= upper/lower - 1；用於直覺理解，不作信號）
- **streak（連續天數）**：bucket_streak=5；pos≥0.80 streak=2；dist_to_upper≤2.0% streak=2
- **forward_mdd(20D)**（bucket=MID_BAND）：p50=-1.637%、p10=-7.279%、min=-31.571%；n=2896（conf=HIGH；conf_decision=OK）

## pos vs dist_to_upper 一致性檢查（提示用；不改數值）
- status: `OK`
- reason: `within_tolerance`

## forward_mdd(20D) 切片分布（閱讀用；不回填主欄位）

- Slice A（pos≥0.80）：p50=-1.508%、p10=-5.431%、min=-31.285% (n=1704, conf=HIGH, conf_decision=OK, min_n_required=200)
- Slice B（dist_to_upper≤2.0%）：p50=-1.443%、p10=-5.486%、min=-31.285% (n=1743, conf=HIGH, conf_decision=OK, min_n_required=200)
- 注意：conf_decision 低於 OK 時，代表樣本數不足以支撐「拿來做決策」；仍可作為閱讀參考。

## forward_mdd(20D) 交集切片（bucket 內；閱讀用；不回填主欄位）

- Slice A_inBucket（bucket=MID_BAND ∩ pos≥0.80）：p50=-1.535%、p10=-5.186%、min=-31.285% (n=638, conf=HIGH, conf_decision=OK, min_n_required=200)
- Slice B_inBucket（bucket=MID_BAND ∩ dist_to_upper≤2.0%）：p50=-1.395%、p10=-5.322%、min=-31.285% (n=718, conf=HIGH, conf_decision=OK, min_n_required=200)
- 說明：交集切片用於回答「在同一個 bucket/regime 內，貼上緣時的 forward_mdd 分布」；避免全樣本切片混入不同 regime。

## 近 5 日（可計算 BB 的交易日；小表）

| date | price_usd | z | pos | bucket | dist_to_upper |
|---|---:|---:|---:|---|---:|
| 2026-02-12 | 145.9600 | 1.0797 | 0.7699 | MID_BAND | 2.266% |
| 2026-02-13 | 146.3400 | 1.1530 | 0.7882 | MID_BAND | 2.059% |
| 2026-02-17 | 146.2900 | 1.1138 | 0.7784 | MID_BAND | 2.102% |
| 2026-02-18 | 147.0100 | 1.2964 | 0.8241 | MID_BAND | 1.626% |
| 2026-02-19 | 146.6800 | 1.2032 | 0.8008 | MID_BAND | 1.732% |

## BB 詳細（可稽核欄位）

| field | value | note |
|---|---:|---|
| price_usd | 146.6800 | adj_close |
| close_usd | 146.6800 | raw close (for reference) |
| z | 1.2032 | log(price) z-score vs BB mean/stdev |
| pos_in_band | 0.8008 | (logp-lower)/(upper-lower) clipped [0,1] |
| lower_usd | 136.8987 | exp(lower_log) |
| upper_usd | 149.2199 | exp(upper_log) |
| dist_to_lower | 6.668% | (price-lower)/price |
| dist_to_upper | 1.732% | (upper-price)/price |
| band_width | 9.000% | (upper/lower - 1) reading-only |
| bucket | MID_BAND | based on z thresholds |

## forward_mdd(20D)（分布解讀）

- 定義：對每一天 t，觀察未來 N 天（t+1..t+N）中的**最低價**相對於當日價的跌幅：min(future)/p0 - 1。
- 理論限制：此值應永遠 <= 0；若 >0，代表對齊/定義錯誤（或資料異常）。
- 你目前看到的是 **bucket=MID_BAND** 條件下的歷史樣本分布（不是預測）。

## FX (USD/TWD)（嚴格同日對齊 + 落後參考值）
- fx_history_parse_status: `OK`
- fx_strict_used_policy: `NA`
- fx_rate_strict (for 2026-02-19): `NA`
- derived price_twd (strict): `NA`

### Reference（僅供參考；使用落後 FX 且標註落後天數）
- fx_ref_source: `HISTORY`
- fx_ref_date: `2026-02-13`
- fx_ref_rate: `31.5000`
- fx_ref_lag_days: `6`
- fx_ref_status: `OK` (stale_threshold_days=30)
- derived price_twd_ref: `4620.42`
- 說明：Reference 不會回填 strict 欄位；它只是一個「在 FX 滯後下的閱讀參考價」。

## Data Quality / Staleness 提示（不改數值，只提示狀態）
- FX strict 缺值，已提供 Reference；lag_days=6。
- 若遇到長假/休市期間，FX strict 為 NA 屬於正常現象；Reference 會明確標註落後天數。

## Notes
- bucket 以 z 門檻定義；pos/dist_to_upper 的閾值僅作閱讀提示，不改信號。
- Δ1D 的基準是「前一個可計算 BB 的交易日」，不是日曆上的昨天。
- forward_mdd20_slices 為閱讀用切片；conf_decision 會在樣本數不足時標示 LOW_FOR_DECISION。
- forward_mdd20_slices_in_bucket 為 bucket 內交集切片，用於避免全樣本切片混入不同 regime。
- pos vs dist_to_upper 一致性檢查為提示用，避免 band_width 或資料異常造成誤讀。
- FX strict 欄位不會用落後匯率填補；落後匯率只會出現在 Reference 區塊。
