# VT BB Monitor Report (VT + optional USD/TWD)

- report_generated_at_utc: `2026-03-06T23:43:06Z`
- data_date: `2026-03-06`
- price_mode: `adj_close`
- params: `BB(60,2.0) on log(price)`, `forward_mdd(20D)`, sidecar=`forward_mdd(10D)`

## 15秒摘要
- **VT** (2026-03-06 price_usd=141.9300) → **MID_BAND** (z=-0.9017, pos=0.2746, pos_raw=0.2746); dist_to_lower=1.993%; dist_to_upper=5.462%; 20D forward_mdd: p50=-1.634%, p10=-7.272%, p5=-10.126%, min=-31.571% (n=2900, conf=HIGH, conf_decision=OK, min_n_required=200)

## Δ1D（一日變動；以前一個「可計算 BB 的交易日」為基準）
- prev_bb_date: `2026-03-05`
- Δprice_1d: -1.142%
- Δz_1d: -0.6433
- Δpos_1d: -0.1608
- Δpos_raw_1d: -0.1608
- Δband_width_1d: -0.123%
- Δdist_to_upper_1d: 1.169%

## 解讀重點（更詳盡）
- **Band 位置**：pos=0.2746（clipped） / pos_raw=0.2746（未截斷；突破上下軌時用於稽核）
- **距離上下軌**：dist_to_upper=5.462%；dist_to_lower=1.993%
- **波動區間寬度（閱讀用）**：band_width≈7.606%（= upper/lower - 1；用於直覺理解，不作信號）
- **streak（連續天數）**：bucket_streak=6；pos≥0.80 streak=0；dist_to_upper≤2.0% streak=0
- **forward_mdd(20D)**（bucket=MID_BAND）：p50=-1.634%、p10=-7.272%、p5=-10.126%、min=-31.571%；n=2900（conf=HIGH；conf_decision=OK）

## pos_raw vs dist_to_upper 一致性檢查（提示用；不改數值）
- status: `OK`
- reason: `within_abs_or_rel_tolerance`
- expected_dist_to_upper(logband): `5.462%`
- abs_err: `0.00000000`; abs_tol: `0.00010000`
- rel_err: `0.000000`; rel_tolerance: `0.020000`

## forward_mdd(20D) 切片分布（閱讀用；不回填主欄位）

- Slice A（pos≥0.80）：p50=-1.511%、p10=-5.421%、p5=-6.987%、min=-31.285% (n=1713, conf=HIGH, conf_decision=OK, min_n_required=200)
- Slice B（dist_to_upper≤2.0%）：p50=-1.446%、p10=-5.476%、p5=-6.987%、min=-31.285% (n=1753, conf=HIGH, conf_decision=OK, min_n_required=200)
- 注意：conf_decision 低於 OK 時，代表樣本數不足以支撐「拿來做決策」；仍可作為閱讀參考。

## forward_mdd(20D) 交集切片（bucket 內；閱讀用；不回填主欄位）

- Slice A_inBucket（bucket=MID_BAND ∩ pos≥0.80）：p50=-1.526%、p10=-5.183%、p5=-6.494%、min=-31.285% (n=640, conf=HIGH, conf_decision=OK, min_n_required=200)
- Slice B_inBucket（bucket=MID_BAND ∩ dist_to_upper≤2.0%）：p50=-1.397%、p10=-5.321%、p5=-6.532%、min=-31.285% (n=721, conf=HIGH, conf_decision=OK, min_n_required=200)
- 說明：交集切片用於回答「在同一個 bucket/regime 內，貼上緣時的 forward_mdd 分布」；避免全樣本切片混入不同 regime。

## forward_mdd(10D) 短窗旁路（閱讀用；不回填主欄位）
- 用途：更貼近「維持率壓力/質押風險」的短期下行行為觀察；不作為主信號。
- bucket=MID_BAND：p50=-0.990%、p10=-4.880%、p5=-6.653%、min=-27.590% (n=2906, conf=HIGH, conf_decision=OK)
- inBucket ∩ pos≥0.80：p10=-3.566%、p5=-5.082% (n=643, conf_decision=OK)
- inBucket ∩ dist_to_upper≤2.0%：p10=-3.277%、p5=-5.055% (n=724, conf_decision=OK)

## band_width 分位數觀察（5-bin；獨立項目；不改 bucket / 不回填主欄位）

- band_width_current: 7.606%; percentile≈26.75; current_bin=`B2(p20-40]`
- quantiles: p20=6.875%, p40=8.959%, p50=9.840%, p60=11.420%, p80=16.683% (n_bw_samples=4392)
- current_bin streak=11

### forward_mdd(20D) × band_width（5-bin 全樣本；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 879 | -1.425% | -6.022% | -8.092% | -11.751% | HIGH | OK |
| B2(p20-40] | 867 | -1.256% | -5.346% | -8.353% | -31.571% | HIGH | OK |
| B3(p40-60] | 869 | -1.811% | -6.439% | -8.671% | -28.032% | HIGH | OK |
| B4(p60-80] | 878 | -1.972% | -8.096% | -9.719% | -31.146% | HIGH | OK |
| B5(>p80) | 879 | -1.996% | -10.218% | -13.989% | -31.574% | HIGH | OK |

### forward_mdd(20D) × band_width（5-bin × bucket=MID_BAND 交集；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 572 | -1.558% | -6.383% | -9.405% | -11.751% | HIGH | OK |
| B2(p20-40] | 570 | -1.167% | -5.262% | -9.427% | -31.571% | HIGH | OK |
| B3(p40-60] | 569 | -1.992% | -6.467% | -9.180% | -27.127% | HIGH | OK |
| B4(p60-80] | 571 | -1.906% | -8.253% | -9.731% | -31.146% | HIGH | OK |
| B5(>p80) | 618 | -1.613% | -9.898% | -13.430% | -25.288% | HIGH | OK |

### forward_mdd(10D) × band_width（5-bin 全樣本；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 879 | -0.733% | -4.058% | -5.380% | -10.991% | HIGH | OK |
| B2(p20-40] | 868 | -0.786% | -3.909% | -5.116% | -17.100% | HIGH | OK |
| B3(p40-60] | 878 | -0.969% | -4.338% | -5.391% | -24.197% | HIGH | OK |
| B4(p60-80] | 878 | -1.230% | -5.294% | -6.887% | -27.590% | HIGH | OK |
| B5(>p80) | 879 | -1.450% | -7.003% | -10.543% | -23.785% | HIGH | OK |

### forward_mdd(10D) × band_width（5-bin × bucket=MID_BAND 交集；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 572 | -0.789% | -4.017% | -5.512% | -10.991% | HIGH | OK |
| B2(p20-40] | 570 | -0.730% | -4.097% | -5.299% | -17.100% | HIGH | OK |
| B3(p40-60] | 575 | -1.101% | -4.651% | -5.421% | -10.740% | HIGH | OK |
| B4(p60-80] | 571 | -1.214% | -5.029% | -7.185% | -27.590% | HIGH | OK |
| B5(>p80) | 618 | -1.224% | -6.476% | -9.367% | -20.108% | HIGH | OK |

- 說明：p5 通常比 min 更穩定；min 容易被單一極端日主宰。這些表格不作為信號，只用於「風險地形」閱讀。

## 近 5 日（可計算 BB 的交易日；小表）

| date | price_usd | z | pos | pos_raw | bucket | dist_to_upper |
|---|---:|---:|---:|---:|---|---:|
| 2026-03-02 | 146.9500 | 1.0152 | 0.7538 | 0.7538 | MID_BAND | 1.950% |
| 2026-03-03 | 144.0400 | -0.0300 | 0.4925 | 0.4925 | MID_BAND | 3.983% |
| 2026-03-04 | 145.2600 | 0.3838 | 0.5960 | 0.5960 | MID_BAND | 3.105% |
| 2026-03-05 | 143.5700 | -0.2584 | 0.4354 | 0.4354 | MID_BAND | 4.293% |
| 2026-03-06 | 141.9300 | -0.9017 | 0.2746 | 0.2746 | MID_BAND | 5.462% |

## BB 詳細（可稽核欄位）

| field | value | note |
|---|---:|---|
| price_usd | 141.9300 | adj_close |
| close_usd | 141.9300 | raw close (for reference) |
| z | -0.9017 | log(price) z-score vs BB mean/stdev |
| pos_in_band | 0.2746 | clipped [0,1] for readability |
| pos_raw | 0.2746 | NOT clipped; can be <0 or >1 when price breaks bands |
| lower_usd | 139.1017 | exp(lower_log) |
| upper_usd | 149.6818 | exp(upper_log) |
| dist_to_lower | 1.993% | (price-lower)/price |
| dist_to_upper | 5.462% | (upper-price)/price |
| band_width | 7.606% | (upper/lower - 1) reading-only |
| bucket | MID_BAND | based on z thresholds |

## forward_mdd（分布解讀）

- 定義：對每一天 t，觀察未來 N 天（t+1..t+N）中的**最低價**相對於當日價的跌幅：min(future)/p0 - 1。
- 理論限制：此值應永遠 <= 0；若 >0，代表對齊/定義錯誤（或資料異常）。
- p5：較穩定的尾部指標（比 min 不那麼容易被單一極端日主宰）。

## FX (USD/TWD)（嚴格同日對齊 + 落後參考值）
- fx_history_parse_status: `OK`
- fx_strict_used_policy: `HISTORY_DATE_MATCH`
- fx_rate_strict (for 2026-03-06): `31.6800`
- derived price_twd (strict): `4496.34`

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
