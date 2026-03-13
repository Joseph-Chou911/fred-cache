# VT BB Monitor Report (VT + optional USD/TWD)

- report_generated_at_utc: `2026-03-13T23:43:53Z`
- data_date: `2026-03-13`
- price_mode: `adj_close`
- params: `BB(60,2.0) on log(price)`, `forward_mdd(20D)`, sidecar=`forward_mdd(10D)`

## 15秒摘要
- **VT** (2026-03-13 price_usd=139.5200) → **NEAR_LOWER_BAND** (z=-1.9647, pos=0.0088, pos_raw=0.0088); dist_to_lower=0.062%; dist_to_upper=7.205%; 20D forward_mdd: p50=-3.138%, p10=-8.865%, p5=-12.388%, min=-31.574% (n=170, conf=HIGH, conf_decision=LOW_FOR_DECISION, min_n_required=200)

## Δ1D（一日變動；以前一個「可計算 BB 的交易日」為基準）
- prev_bb_date: `2026-03-12`
- Δprice_1d: -0.733%
- Δz_1d: -0.4038
- Δpos_1d: -0.1010
- Δpos_raw_1d: -0.1010
- Δband_width_1d: 0.055%
- Δdist_to_upper_1d: 0.806%

## 解讀重點（更詳盡）
- **Band 位置**：pos=0.0088（clipped） / pos_raw=0.0088（未截斷；突破上下軌時用於稽核）
- **距離上下軌**：dist_to_upper=7.205%；dist_to_lower=0.062%
- **波動區間寬度（閱讀用）**：band_width≈7.272%（= upper/lower - 1；用於直覺理解，不作信號）
- **streak（連續天數）**：bucket_streak=2；pos≥0.80 streak=0；dist_to_upper≤2.0% streak=0
- **forward_mdd(20D)**（bucket=NEAR_LOWER_BAND）：p50=-3.138%、p10=-8.865%、p5=-12.388%、min=-31.574%；n=170（conf=HIGH；conf_decision=LOW_FOR_DECISION）

## pos_raw vs dist_to_upper 一致性檢查（提示用；不改數值）
- status: `OK`
- reason: `within_abs_or_rel_tolerance`
- expected_dist_to_upper(logband): `7.205%`
- abs_err: `0.00000000`; abs_tol: `0.00010000`
- rel_err: `0.000000`; rel_tolerance: `0.020000`

## forward_mdd(20D) 切片分布（閱讀用；不回填主欄位）

- Slice A（pos≥0.80）：p50=-1.515%、p10=-5.415%、p5=-6.983%、min=-31.285% (n=1717, conf=HIGH, conf_decision=OK, min_n_required=200)
- Slice B（dist_to_upper≤2.0%）：p50=-1.448%、p10=-5.467%、p5=-6.983%、min=-31.285% (n=1757, conf=HIGH, conf_decision=OK, min_n_required=200)
- 注意：conf_decision 低於 OK 時，代表樣本數不足以支撐「拿來做決策」；仍可作為閱讀參考。

## forward_mdd(20D) 交集切片（bucket 內；閱讀用；不回填主欄位）

- Slice A_inBucket（bucket=NEAR_LOWER_BAND ∩ pos≥0.80）：p50=NA、p10=NA、p5=NA、min=NA (n=0, conf=NA, conf_decision=NA, min_n_required=200)
- Slice B_inBucket（bucket=NEAR_LOWER_BAND ∩ dist_to_upper≤2.0%）：p50=NA、p10=NA、p5=NA、min=NA (n=0, conf=NA, conf_decision=NA, min_n_required=200)
- 說明：交集切片用於回答「在同一個 bucket/regime 內，貼上緣時的 forward_mdd 分布」；避免全樣本切片混入不同 regime。

## forward_mdd(10D) 短窗旁路（閱讀用；不回填主欄位）
- 用途：更貼近「維持率壓力/質押風險」的短期下行行為觀察；不作為主信號。
- bucket=NEAR_LOWER_BAND：p50=-1.978%、p10=-7.324%、p5=-12.096%、min=-25.941% (n=170, conf=HIGH, conf_decision=LOW_FOR_DECISION)
- inBucket ∩ pos≥0.80：p10=NA、p5=NA (n=0, conf_decision=NA)
- inBucket ∩ dist_to_upper≤2.0%：p10=NA、p5=NA (n=0, conf_decision=NA)

## band_width 分位數觀察（5-bin；獨立項目；不改 bucket / 不回填主欄位）

- band_width_current: 7.272%; percentile≈23.63; current_bin=`B2(p20-40]`
- quantiles: p20=6.876%, p40=8.953%, p50=9.835%, p60=11.414%, p80=16.667% (n_bw_samples=4397)
- current_bin streak=16

### forward_mdd(20D) × band_width（5-bin 全樣本；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 880 | -1.423% | -6.019% | -8.085% | -11.751% | HIGH | OK |
| B2(p20-40] | 863 | -1.260% | -5.348% | -8.368% | -31.571% | HIGH | OK |
| B3(p40-60] | 875 | -1.828% | -6.431% | -8.655% | -28.032% | HIGH | OK |
| B4(p60-80] | 879 | -1.969% | -8.096% | -9.718% | -31.146% | HIGH | OK |
| B5(>p80) | 880 | -1.991% | -10.217% | -13.988% | -31.574% | HIGH | OK |

### forward_mdd(20D) × band_width（5-bin × bucket=NEAR_LOWER_BAND 交集；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 27 | -3.120% | -5.979% | -7.849% | -8.749% | LOW | LOW_FOR_DECISION |
| B2(p20-40] | 20 | -1.086% | -11.041% | -11.198% | -12.476% | LOW | LOW_FOR_DECISION |
| B3(p40-60] | 19 | -0.811% | -6.577% | -7.153% | -8.196% | NA | LOW_FOR_DECISION |
| B4(p60-80] | 38 | -4.970% | -7.924% | -11.574% | -28.985% | LOW | LOW_FOR_DECISION |
| B5(>p80) | 66 | -3.061% | -12.227% | -15.388% | -31.574% | MED | LOW_FOR_DECISION |

### forward_mdd(10D) × band_width（5-bin 全樣本；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 880 | -0.733% | -4.058% | -5.377% | -10.991% | HIGH | OK |
| B2(p20-40] | 869 | -0.800% | -3.984% | -5.190% | -17.100% | HIGH | OK |
| B3(p40-60] | 879 | -0.972% | -4.335% | -5.389% | -24.197% | HIGH | OK |
| B4(p60-80] | 879 | -1.227% | -5.292% | -6.887% | -27.590% | HIGH | OK |
| B5(>p80) | 880 | -1.445% | -6.983% | -10.536% | -23.785% | HIGH | OK |

### forward_mdd(10D) × band_width（5-bin × bucket=NEAR_LOWER_BAND 交集；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 27 | -2.755% | -5.591% | -6.620% | -8.635% | LOW | LOW_FOR_DECISION |
| B2(p20-40] | 20 | -1.031% | -10.941% | -11.103% | -12.476% | LOW | LOW_FOR_DECISION |
| B3(p40-60] | 19 | -0.811% | -3.514% | -4.244% | -6.362% | NA | LOW_FOR_DECISION |
| B4(p60-80] | 38 | -3.890% | -6.835% | -9.453% | -25.941% | LOW | LOW_FOR_DECISION |
| B5(>p80) | 66 | -2.119% | -11.632% | -15.388% | -23.785% | MED | LOW_FOR_DECISION |

- 說明：p5 通常比 min 更穩定；min 容易被單一極端日主宰。這些表格不作為信號，只用於「風險地形」閱讀。

## 近 5 日（可計算 BB 的交易日；小表）

| date | price_usd | z | pos | pos_raw | bucket | dist_to_upper |
|---|---:|---:|---:|---:|---|---:|
| 2026-03-09 | 143.2400 | -0.4323 | 0.3919 | 0.3919 | MID_BAND | 4.449% |
| 2026-03-10 | 143.2200 | -0.4601 | 0.3850 | 0.3850 | MID_BAND | 4.443% |
| 2026-03-11 | 143.0400 | -0.5470 | 0.3632 | 0.3632 | MID_BAND | 4.560% |
| 2026-03-12 | 140.5500 | -1.5609 | 0.1098 | 0.1098 | NEAR_LOWER_BAND | 6.400% |
| 2026-03-13 | 139.5200 | -1.9647 | 0.0088 | 0.0088 | NEAR_LOWER_BAND | 7.205% |

## BB 詳細（可稽核欄位）

| field | value | note |
|---|---:|---|
| price_usd | 139.5200 | adj_close |
| close_usd | 139.5200 | raw close (for reference) |
| z | -1.9647 | log(price) z-score vs BB mean/stdev |
| pos_in_band | 0.0088 | clipped [0,1] for readability |
| pos_raw | 0.0088 | NOT clipped; can be <0 or >1 when price breaks bands |
| lower_usd | 139.4337 | exp(lower_log) |
| upper_usd | 149.5729 | exp(upper_log) |
| dist_to_lower | 0.062% | (price-lower)/price |
| dist_to_upper | 7.205% | (upper-price)/price |
| band_width | 7.272% | (upper/lower - 1) reading-only |
| bucket | NEAR_LOWER_BAND | based on z thresholds |

## forward_mdd（分布解讀）

- 定義：對每一天 t，觀察未來 N 天（t+1..t+N）中的**最低價**相對於當日價的跌幅：min(future)/p0 - 1。
- 理論限制：此值應永遠 <= 0；若 >0，代表對齊/定義錯誤（或資料異常）。
- p5：較穩定的尾部指標（比 min 不那麼容易被單一極端日主宰）。

## FX (USD/TWD)（嚴格同日對齊 + 落後參考值）
- fx_history_parse_status: `OK`
- fx_strict_used_policy: `HISTORY_DATE_MATCH`
- fx_rate_strict (for 2026-03-13): `31.9150`
- derived price_twd (strict): `4452.78`

### Reference（僅供參考；使用落後 FX 且標註落後天數）
- fx_ref: `NA` (strict match exists, or no usable reference rate)

## Data Quality / Staleness 提示（不改數值，只提示狀態）
- FX strict 有值（同日對齊成立）或無可用參考。
- 若遇到長假/休市期間，FX strict 為 NA 屬於正常現象；Reference 會明確標註落後天數。

## Notes
- bucket 以 z 門檻定義；pos/dist_to_upper 的閾值僅作閱讀提示，不改信號。
- Δ1D 的基準是「前一個可計算 BB 的交易日」，不是日曆上的昨天。
- forward_mdd 切片（含 in-bucket / band_width 5-bin）為閱讀用；conf_decision 會在樣本數不足時標示 LOW_FOR_DECISION。
- pos_raw vs dist_to_upper 一致性檢查採 logband 幾何一致性，並用 abs+rel 雙門檻避免 near-zero 相對誤差放大。
- FX strict 欄位不會用落後匯率填補；落後匯率只會出現在 Reference 區塊。
