# VT BB Monitor Report (VT + optional USD/TWD)

- report_generated_at_utc: `2026-02-20T06:14:07Z`
- data_date: `2026-02-19`
- price_mode: `adj_close`
- params: `BB(60,2.0) on log(price)`, `forward_mdd(20D)`, sidecar=`forward_mdd(10D)`

## 15秒摘要
- **VT** (2026-02-19 price_usd=146.6800) → **MID_BAND** (z=1.2032, pos=0.8008, pos_raw=0.8008); dist_to_lower=6.668%; dist_to_upper=1.732%; 20D forward_mdd: p50=-1.637%, p10=-7.279%, p5=-10.128%, min=-31.571% (n=2896, conf=HIGH, conf_decision=OK, min_n_required=200)

## Δ1D（一日變動；以前一個「可計算 BB 的交易日」為基準）
- prev_bb_date: `2026-02-18`
- Δprice_1d: -0.224%
- Δz_1d: -0.0933
- Δpos_1d: -0.0233
- Δpos_raw_1d: -0.0233
- Δband_width_1d: -0.603%
- Δdist_to_upper_1d: 0.106%

## 解讀重點（更詳盡）
- **Band 位置**：pos=0.8008（clipped） / pos_raw=0.8008（未截斷；突破上下軌時用於稽核）
- **距離上下軌**：dist_to_upper=1.732%；dist_to_lower=6.668%
- **波動區間寬度（閱讀用）**：band_width≈9.000%（= upper/lower - 1；用於直覺理解，不作信號）
- **streak（連續天數）**：bucket_streak=5；pos≥0.80 streak=2；dist_to_upper≤2.0% streak=2
- **forward_mdd(20D)**（bucket=MID_BAND）：p50=-1.637%、p10=-7.279%、p5=-10.128%、min=-31.571%；n=2896（conf=HIGH；conf_decision=OK）

## pos_raw vs dist_to_upper 一致性檢查（提示用；不改數值）
- status: `OK`
- reason: `within_abs_or_rel_tolerance`
- expected_dist_to_upper(logband): `1.732%`
- abs_err: `0.00000000`; abs_tol: `0.00010000`
- rel_err: `0.000000`; rel_tolerance: `0.020000`

## forward_mdd(20D) 切片分布（閱讀用；不回填主欄位）

- Slice A（pos≥0.80）：p50=-1.508%、p10=-5.431%、p5=-6.999%、min=-31.285% (n=1704, conf=HIGH, conf_decision=OK, min_n_required=200)
- Slice B（dist_to_upper≤2.0%）：p50=-1.443%、p10=-5.486%、p5=-7.000%、min=-31.285% (n=1743, conf=HIGH, conf_decision=OK, min_n_required=200)
- 注意：conf_decision 低於 OK 時，代表樣本數不足以支撐「拿來做決策」；仍可作為閱讀參考。

## forward_mdd(20D) 交集切片（bucket 內；閱讀用；不回填主欄位）

- Slice A_inBucket（bucket=MID_BAND ∩ pos≥0.80）：p50=-1.535%、p10=-5.186%、p5=-6.497%、min=-31.285% (n=638, conf=HIGH, conf_decision=OK, min_n_required=200)
- Slice B_inBucket（bucket=MID_BAND ∩ dist_to_upper≤2.0%）：p50=-1.395%、p10=-5.322%、p5=-6.543%、min=-31.285% (n=718, conf=HIGH, conf_decision=OK, min_n_required=200)
- 說明：交集切片用於回答「在同一個 bucket/regime 內，貼上緣時的 forward_mdd 分布」；避免全樣本切片混入不同 regime。

## forward_mdd(10D) 短窗旁路（閱讀用；不回填主欄位）
- 用途：更貼近「維持率壓力/質押風險」的短期下行行為觀察；不作為主信號。
- bucket=MID_BAND：p50=-0.991%、p10=-4.903%、p5=-6.666%、min=-27.590% (n=2899, conf=HIGH, conf_decision=OK)
- inBucket ∩ pos≥0.80：p10=-3.569%、p5=-5.083% (n=640, conf_decision=OK)
- inBucket ∩ dist_to_upper≤2.0%：p10=-3.278%、p5=-5.061% (n=721, conf_decision=OK)

## band_width 分位數觀察（5-bin；獨立項目；不改 bucket / 不回填主欄位）

- band_width_current: 9.000%; percentile≈40.45; current_bin=`B3(p40-60]`
- quantiles: p20=6.870%, p40=8.970%, p50=9.855%, p60=11.445%, p80=16.701% (n_bw_samples=4381)
- current_bin streak=15

### forward_mdd(20D) × band_width（5-bin 全樣本；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 877 | -1.422% | -6.028% | -8.106% | -11.751% | HIGH | OK |
| B2(p20-40] | 871 | -1.263% | -5.414% | -8.739% | -31.571% | HIGH | OK |
| B3(p40-60] | 861 | -1.801% | -6.396% | -8.600% | -28.032% | HIGH | OK |
| B4(p60-80] | 876 | -1.975% | -8.096% | -9.723% | -31.146% | HIGH | OK |
| B5(>p80) | 876 | -1.991% | -10.218% | -13.990% | -31.574% | HIGH | OK |

### forward_mdd(20D) × band_width（5-bin × bucket=MID_BAND 交集；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 570 | -1.531% | -6.397% | -9.412% | -11.751% | HIGH | OK |
| B2(p20-40] | 575 | -1.204% | -5.335% | -11.197% | -31.571% | HIGH | OK |
| B3(p40-60] | 565 | -1.992% | -6.446% | -8.952% | -18.618% | HIGH | OK |
| B4(p60-80] | 568 | -1.900% | -8.280% | -9.736% | -31.146% | HIGH | OK |
| B5(>p80) | 618 | -1.613% | -9.898% | -13.430% | -25.288% | HIGH | OK |

### forward_mdd(10D) × band_width（5-bin 全樣本；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 877 | -0.733% | -4.060% | -5.386% | -10.991% | HIGH | OK |
| B2(p20-40] | 876 | -0.795% | -3.964% | -5.157% | -17.100% | HIGH | OK |
| B3(p40-60] | 866 | -0.939% | -4.292% | -5.360% | -24.197% | HIGH | OK |
| B4(p60-80] | 876 | -1.260% | -5.314% | -6.888% | -27.590% | HIGH | OK |
| B5(>p80) | 876 | -1.440% | -7.066% | -10.562% | -23.785% | HIGH | OK |

### forward_mdd(10D) × band_width（5-bin × bucket=MID_BAND 交集；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 570 | -0.783% | -4.025% | -5.517% | -10.991% | HIGH | OK |
| B2(p20-40] | 575 | -0.737% | -4.110% | -5.483% | -17.100% | HIGH | OK |
| B3(p40-60] | 568 | -1.097% | -4.592% | -5.409% | -7.447% | HIGH | OK |
| B4(p60-80] | 568 | -1.217% | -5.041% | -7.273% | -27.590% | HIGH | OK |
| B5(>p80) | 618 | -1.224% | -6.476% | -9.367% | -20.108% | HIGH | OK |

- 說明：p5 通常比 min 更穩定；min 容易被單一極端日主宰。這些表格不作為信號，只用於「風險地形」閱讀。

## 近 5 日（可計算 BB 的交易日；小表）

| date | price_usd | z | pos | pos_raw | bucket | dist_to_upper |
|---|---:|---:|---:|---:|---|---:|
| 2026-02-12 | 145.9600 | 1.0797 | 0.7699 | 0.7699 | MID_BAND | 2.266% |
| 2026-02-13 | 146.3400 | 1.1530 | 0.7882 | 0.7882 | MID_BAND | 2.059% |
| 2026-02-17 | 146.2900 | 1.1138 | 0.7784 | 0.7784 | MID_BAND | 2.102% |
| 2026-02-18 | 147.0100 | 1.2964 | 0.8241 | 0.8241 | MID_BAND | 1.626% |
| 2026-02-19 | 146.6800 | 1.2032 | 0.8008 | 0.8008 | MID_BAND | 1.732% |

## BB 詳細（可稽核欄位）

| field | value | note |
|---|---:|---|
| price_usd | 146.6800 | adj_close |
| close_usd | 146.6800 | raw close (for reference) |
| z | 1.2032 | log(price) z-score vs BB mean/stdev |
| pos_in_band | 0.8008 | clipped [0,1] for readability |
| pos_raw | 0.8008 | NOT clipped; can be <0 or >1 when price breaks bands |
| lower_usd | 136.8987 | exp(lower_log) |
| upper_usd | 149.2199 | exp(upper_log) |
| dist_to_lower | 6.668% | (price-lower)/price |
| dist_to_upper | 1.732% | (upper-price)/price |
| band_width | 9.000% | (upper/lower - 1) reading-only |
| bucket | MID_BAND | based on z thresholds |

## forward_mdd（分布解讀）

- 定義：對每一天 t，觀察未來 N 天（t+1..t+N）中的**最低價**相對於當日價的跌幅：min(future)/p0 - 1。
- 理論限制：此值應永遠 <= 0；若 >0，代表對齊/定義錯誤（或資料異常）。
- p5：較穩定的尾部指標（比 min 不那麼容易被單一極端日主宰）。

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
- forward_mdd 切片（含 in-bucket / band_width 5-bin）為閱讀用；conf_decision 會在樣本數不足時標示 LOW_FOR_DECISION。
- pos_raw vs dist_to_upper 一致性檢查採 logband 幾何一致性，並用 abs+rel 雙門檻避免 near-zero 相對誤差放大。
- FX strict 欄位不會用落後匯率填補；落後匯率只會出現在 Reference 區塊。
