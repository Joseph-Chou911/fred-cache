# VT BB Monitor Report (VT + optional USD/TWD)

- report_generated_at_utc: `2026-02-26T23:46:31Z`
- data_date: `2026-02-26`
- price_mode: `adj_close`
- params: `BB(60,2.0) on log(price)`, `forward_mdd(20D)`, sidecar=`forward_mdd(10D)`

## 15秒摘要
- **VT** (2026-02-26 price_usd=148.4000) → **NEAR_UPPER_BAND** (z=1.5779, pos=0.8945, pos_raw=0.8945); dist_to_lower=6.919%; dist_to_upper=0.849%; 20D forward_mdd: p50=-1.578%, p10=-5.617%, p5=-6.890%, min=-27.390% (n=831, conf=HIGH, conf_decision=OK, min_n_required=200)

## Δ1D（一日變動；以前一個「可計算 BB 的交易日」為基準）
- prev_bb_date: `2026-02-25`
- Δprice_1d: -0.342%
- Δz_1d: -0.2308
- Δpos_1d: -0.0577
- Δpos_raw_1d: -0.0577
- Δband_width_1d: 0.047%
- Δdist_to_upper_1d: 0.467%

## 解讀重點（更詳盡）
- **Band 位置**：pos=0.8945（clipped） / pos_raw=0.8945（未截斷；突破上下軌時用於稽核）
- **距離上下軌**：dist_to_upper=0.849%；dist_to_lower=6.919%
- **波動區間寬度（閱讀用）**：band_width≈8.346%（= upper/lower - 1；用於直覺理解，不作信號）
- **streak（連續天數）**：bucket_streak=2；pos≥0.80 streak=3；dist_to_upper≤2.0% streak=7
- **forward_mdd(20D)**（bucket=NEAR_UPPER_BAND）：p50=-1.578%、p10=-5.617%、p5=-6.890%、min=-27.390%；n=831（conf=HIGH；conf_decision=OK）

## pos_raw vs dist_to_upper 一致性檢查（提示用；不改數值）
- status: `OK`
- reason: `within_abs_or_rel_tolerance`
- expected_dist_to_upper(logband): `0.849%`
- abs_err: `0.00000000`; abs_tol: `0.00010000`
- rel_err: `0.000000`; rel_tolerance: `0.020000`

## forward_mdd(20D) 切片分布（閱讀用；不回填主欄位）

- Slice A（pos≥0.80）：p50=-1.509%、p10=-5.426%、p5=-6.992%、min=-31.285% (n=1709, conf=HIGH, conf_decision=OK, min_n_required=200)
- Slice B（dist_to_upper≤2.0%）：p50=-1.445%、p10=-5.483%、p5=-6.994%、min=-31.285% (n=1748, conf=HIGH, conf_decision=OK, min_n_required=200)
- 注意：conf_decision 低於 OK 時，代表樣本數不足以支撐「拿來做決策」；仍可作為閱讀參考。

## forward_mdd(20D) 交集切片（bucket 內；閱讀用；不回填主欄位）

- Slice A_inBucket（bucket=NEAR_UPPER_BAND ∩ pos≥0.80）：p50=-1.578%、p10=-5.617%、p5=-6.890%、min=-27.390% (n=831, conf=HIGH, conf_decision=OK, min_n_required=200)
- Slice B_inBucket（bucket=NEAR_UPPER_BAND ∩ dist_to_upper≤2.0%）：p50=-1.535%、p10=-5.484%、p5=-6.831%、min=-27.390% (n=790, conf=HIGH, conf_decision=OK, min_n_required=200)
- 說明：交集切片用於回答「在同一個 bucket/regime 內，貼上緣時的 forward_mdd 分布」；避免全樣本切片混入不同 regime。

## forward_mdd(10D) 短窗旁路（閱讀用；不回填主欄位）
- 用途：更貼近「維持率壓力/質押風險」的短期下行行為觀察；不作為主信號。
- bucket=NEAR_UPPER_BAND：p50=-0.882%、p10=-3.626%、p5=-4.556%、min=-10.773% (n=836, conf=HIGH, conf_decision=OK)
- inBucket ∩ pos≥0.80：p10=-3.626%、p5=-4.556% (n=836, conf_decision=OK)
- inBucket ∩ dist_to_upper≤2.0%：p10=-3.552%、p5=-4.472% (n=795, conf_decision=OK)

## band_width 分位數觀察（5-bin；獨立項目；不改 bucket / 不回填主欄位）

- band_width_current: 8.346%; percentile≈33.90; current_bin=`B2(p20-40]`
- quantiles: p20=6.872%, p40=8.965%, p50=9.849%, p60=11.425%, p80=16.700% (n_bw_samples=4386)
- current_bin streak=5

### forward_mdd(20D) × band_width（5-bin 全樣本；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 878 | -1.423% | -6.025% | -8.099% | -11.751% | HIGH | OK |
| B2(p20-40] | 872 | -1.260% | -5.403% | -8.595% | -31.571% | HIGH | OK |
| B3(p40-60] | 862 | -1.814% | -6.421% | -8.632% | -28.032% | HIGH | OK |
| B4(p60-80] | 877 | -1.969% | -8.096% | -9.721% | -31.146% | HIGH | OK |
| B5(>p80) | 877 | -1.996% | -10.218% | -13.990% | -31.574% | HIGH | OK |

### forward_mdd(20D) × band_width（5-bin × bucket=NEAR_UPPER_BAND 交集；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 151 | -0.939% | -5.871% | -6.871% | -10.064% | HIGH | LOW_FOR_DECISION |
| B2(p20-40] | 187 | -1.117% | -3.819% | -5.578% | -27.390% | HIGH | LOW_FOR_DECISION |
| B3(p40-60] | 196 | -1.437% | -4.634% | -6.582% | -10.738% | HIGH | LOW_FOR_DECISION |
| B4(p60-80] | 180 | -1.744% | -6.660% | -8.295% | -11.802% | HIGH | LOW_FOR_DECISION |
| B5(>p80) | 117 | -2.429% | -5.844% | -6.351% | -7.811% | MED | LOW_FOR_DECISION |

### forward_mdd(10D) × band_width（5-bin 全樣本；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 878 | -0.733% | -4.059% | -5.383% | -10.991% | HIGH | OK |
| B2(p20-40] | 872 | -0.787% | -3.942% | -5.176% | -17.100% | HIGH | OK |
| B3(p40-60] | 872 | -0.959% | -4.293% | -5.352% | -24.197% | HIGH | OK |
| B4(p60-80] | 877 | -1.237% | -5.313% | -6.888% | -27.590% | HIGH | OK |
| B5(>p80) | 877 | -1.440% | -7.045% | -10.556% | -23.785% | HIGH | OK |

### forward_mdd(10D) × band_width（5-bin × bucket=NEAR_UPPER_BAND 交集；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 151 | -0.668% | -3.295% | -4.000% | -7.069% | HIGH | LOW_FOR_DECISION |
| B2(p20-40] | 187 | -0.714% | -2.845% | -3.757% | -10.773% | HIGH | LOW_FOR_DECISION |
| B3(p40-60] | 201 | -0.838% | -3.167% | -3.743% | -8.523% | HIGH | OK |
| B4(p60-80] | 180 | -0.932% | -3.942% | -5.095% | -9.131% | HIGH | LOW_FOR_DECISION |
| B5(>p80) | 117 | -1.699% | -4.636% | -5.616% | -7.459% | MED | LOW_FOR_DECISION |

- 說明：p5 通常比 min 更穩定；min 容易被單一極端日主宰。這些表格不作為信號，只用於「風險地形」閱讀。

## 近 5 日（可計算 BB 的交易日；小表）

| date | price_usd | z | pos | pos_raw | bucket | dist_to_upper |
|---|---:|---:|---:|---:|---|---:|
| 2026-02-20 | 147.9500 | 1.5954 | 0.8989 | 0.8989 | NEAR_UPPER_BAND | 0.841% |
| 2026-02-23 | 146.6500 | 1.1492 | 0.7873 | 0.7873 | MID_BAND | 1.720% |
| 2026-02-24 | 147.7000 | 1.4672 | 0.8668 | 0.8668 | MID_BAND | 1.060% |
| 2026-02-25 | 148.9100 | 1.8087 | 0.9522 | 0.9522 | NEAR_UPPER_BAND | 0.382% |
| 2026-02-26 | 148.4000 | 1.5779 | 0.8945 | 0.8945 | NEAR_UPPER_BAND | 0.849% |

## BB 詳細（可稽核欄位）

| field | value | note |
|---|---:|---|
| price_usd | 148.4000 | adj_close |
| close_usd | 148.4000 | raw close (for reference) |
| z | 1.5779 | log(price) z-score vs BB mean/stdev |
| pos_in_band | 0.8945 | clipped [0,1] for readability |
| pos_raw | 0.8945 | NOT clipped; can be <0 or >1 when price breaks bands |
| lower_usd | 138.1316 | exp(lower_log) |
| upper_usd | 149.6605 | exp(upper_log) |
| dist_to_lower | 6.919% | (price-lower)/price |
| dist_to_upper | 0.849% | (upper-price)/price |
| band_width | 8.346% | (upper/lower - 1) reading-only |
| bucket | NEAR_UPPER_BAND | based on z thresholds |

## forward_mdd（分布解讀）

- 定義：對每一天 t，觀察未來 N 天（t+1..t+N）中的**最低價**相對於當日價的跌幅：min(future)/p0 - 1。
- 理論限制：此值應永遠 <= 0；若 >0，代表對齊/定義錯誤（或資料異常）。
- p5：較穩定的尾部指標（比 min 不那麼容易被單一極端日主宰）。

## FX (USD/TWD)（嚴格同日對齊 + 落後參考值）
- fx_history_parse_status: `OK`
- fx_strict_used_policy: `HISTORY_DATE_MATCH`
- fx_rate_strict (for 2026-02-26): `31.2200`
- derived price_twd (strict): `4633.05`

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
