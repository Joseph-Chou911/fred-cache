# VT BB Monitor Report (VT + optional USD/TWD)

- report_generated_at_utc: `2026-02-24T23:06:33Z`
- data_date: `2026-02-24`
- price_mode: `adj_close`
- params: `BB(60,2.0) on log(price)`, `forward_mdd(20D)`, sidecar=`forward_mdd(10D)`

## 15秒摘要
- **VT** (2026-02-24 price_usd=147.7000) → **MID_BAND** (z=1.4672, pos=0.8668, pos_raw=0.8668); dist_to_lower=6.630%; dist_to_upper=1.060%; 20D forward_mdd: p50=-1.637%, p10=-7.279%, p5=-10.128%, min=-31.571% (n=2896, conf=HIGH, conf_decision=OK, min_n_required=200)

## Δ1D（一日變動；以前一個「可計算 BB 的交易日」為基準）
- prev_bb_date: `2026-02-23`
- Δprice_1d: 0.716%
- Δz_1d: 0.3180
- Δpos_1d: 0.0795
- Δpos_raw_1d: 0.0795
- Δband_width_1d: -0.110%
- Δdist_to_upper_1d: -0.660%

## 解讀重點（更詳盡）
- **Band 位置**：pos=0.8668（clipped） / pos_raw=0.8668（未截斷；突破上下軌時用於稽核）
- **距離上下軌**：dist_to_upper=1.060%；dist_to_lower=6.630%
- **波動區間寬度（閱讀用）**：band_width≈8.236%（= upper/lower - 1；用於直覺理解，不作信號）
- **streak（連續天數）**：bucket_streak=2；pos≥0.80 streak=1；dist_to_upper≤2.0% streak=5
- **forward_mdd(20D)**（bucket=MID_BAND）：p50=-1.637%、p10=-7.279%、p5=-10.128%、min=-31.571%；n=2896（conf=HIGH；conf_decision=OK）

## pos_raw vs dist_to_upper 一致性檢查（提示用；不改數值）
- status: `OK`
- reason: `within_abs_or_rel_tolerance`
- expected_dist_to_upper(logband): `1.060%`
- abs_err: `0.00000000`; abs_tol: `0.00010000`
- rel_err: `0.000000`; rel_tolerance: `0.020000`

## forward_mdd(20D) 切片分布（閱讀用；不回填主欄位）

- Slice A（pos≥0.80）：p50=-1.508%、p10=-5.428%、p5=-6.995%、min=-31.285% (n=1707, conf=HIGH, conf_decision=OK, min_n_required=200)
- Slice B（dist_to_upper≤2.0%）：p50=-1.443%、p10=-5.484%、p5=-6.996%、min=-31.285% (n=1746, conf=HIGH, conf_decision=OK, min_n_required=200)
- 注意：conf_decision 低於 OK 時，代表樣本數不足以支撐「拿來做決策」；仍可作為閱讀參考。

## forward_mdd(20D) 交集切片（bucket 內；閱讀用；不回填主欄位）

- Slice A_inBucket（bucket=MID_BAND ∩ pos≥0.80）：p50=-1.535%、p10=-5.186%、p5=-6.497%、min=-31.285% (n=638, conf=HIGH, conf_decision=OK, min_n_required=200)
- Slice B_inBucket（bucket=MID_BAND ∩ dist_to_upper≤2.0%）：p50=-1.395%、p10=-5.322%、p5=-6.543%、min=-31.285% (n=718, conf=HIGH, conf_decision=OK, min_n_required=200)
- 說明：交集切片用於回答「在同一個 bucket/regime 內，貼上緣時的 forward_mdd 分布」；避免全樣本切片混入不同 regime。

## forward_mdd(10D) 短窗旁路（閱讀用；不回填主欄位）
- 用途：更貼近「維持率壓力/質押風險」的短期下行行為觀察；不作為主信號。
- bucket=MID_BAND：p50=-0.990%、p10=-4.903%、p5=-6.665%、min=-27.590% (n=2901, conf=HIGH, conf_decision=OK)
- inBucket ∩ pos≥0.80：p10=-3.569%、p5=-5.082% (n=641, conf_decision=OK)
- inBucket ∩ dist_to_upper≤2.0%：p10=-3.277%、p5=-5.059% (n=722, conf_decision=OK)

## band_width 分位數觀察（5-bin；獨立項目；不改 bucket / 不回填主欄位）

- band_width_current: 8.236%; percentile≈32.89; current_bin=`B2(p20-40]`
- quantiles: p20=6.871%, p40=8.966%, p50=9.849%, p60=11.426%, p80=16.700% (n_bw_samples=4384)
- current_bin streak=3

### forward_mdd(20D) × band_width（5-bin 全樣本；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 877 | -1.422% | -6.028% | -8.106% | -11.751% | HIGH | OK |
| B2(p20-40] | 872 | -1.260% | -5.403% | -8.595% | -31.571% | HIGH | OK |
| B3(p40-60] | 861 | -1.811% | -6.424% | -8.634% | -28.032% | HIGH | OK |
| B4(p60-80] | 877 | -1.969% | -8.096% | -9.721% | -31.146% | HIGH | OK |
| B5(>p80) | 877 | -1.996% | -10.218% | -13.990% | -31.574% | HIGH | OK |

### forward_mdd(20D) × band_width（5-bin × bucket=MID_BAND 交集；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 570 | -1.531% | -6.397% | -9.412% | -11.751% | HIGH | OK |
| B2(p20-40] | 574 | -1.189% | -5.301% | -10.460% | -31.571% | HIGH | OK |
| B3(p40-60] | 565 | -1.998% | -6.461% | -9.079% | -18.618% | HIGH | OK |
| B4(p60-80] | 569 | -1.894% | -8.271% | -9.734% | -31.146% | HIGH | OK |
| B5(>p80) | 618 | -1.613% | -9.898% | -13.430% | -25.288% | HIGH | OK |

### forward_mdd(10D) × band_width（5-bin 全樣本；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 877 | -0.733% | -4.060% | -5.386% | -10.991% | HIGH | OK |
| B2(p20-40] | 874 | -0.789% | -3.931% | -5.166% | -17.100% | HIGH | OK |
| B3(p40-60] | 869 | -0.946% | -4.301% | -5.356% | -24.197% | HIGH | OK |
| B4(p60-80] | 877 | -1.237% | -5.313% | -6.888% | -27.590% | HIGH | OK |
| B5(>p80) | 877 | -1.440% | -7.045% | -10.556% | -23.785% | HIGH | OK |

### forward_mdd(10D) × band_width（5-bin × bucket=MID_BAND 交集；閱讀用）

| bw_bin | n | p50 | p10 | p5 | min | conf | conf_decision |
|---|---:|---:|---:|---:|---:|---|---|
| B1(<=p20) | 570 | -0.783% | -4.025% | -5.517% | -10.991% | HIGH | OK |
| B2(p20-40] | 574 | -0.736% | -4.099% | -5.507% | -17.100% | HIGH | OK |
| B3(p40-60] | 570 | -1.097% | -4.625% | -5.405% | -7.447% | HIGH | OK |
| B4(p60-80] | 569 | -1.214% | -5.037% | -7.244% | -27.590% | HIGH | OK |
| B5(>p80) | 618 | -1.224% | -6.476% | -9.367% | -20.108% | HIGH | OK |

- 說明：p5 通常比 min 更穩定；min 容易被單一極端日主宰。這些表格不作為信號，只用於「風險地形」閱讀。

## 近 5 日（可計算 BB 的交易日；小表）

| date | price_usd | z | pos | pos_raw | bucket | dist_to_upper |
|---|---:|---:|---:|---:|---|---:|
| 2026-02-18 | 147.0100 | 1.2964 | 0.8241 | 0.8241 | MID_BAND | 1.626% |
| 2026-02-19 | 146.6800 | 1.2032 | 0.8008 | 0.8008 | MID_BAND | 1.732% |
| 2026-02-20 | 147.9500 | 1.5954 | 0.8989 | 0.8989 | NEAR_UPPER_BAND | 0.841% |
| 2026-02-23 | 146.6500 | 1.1492 | 0.7873 | 0.7873 | MID_BAND | 1.720% |
| 2026-02-24 | 147.7000 | 1.4672 | 0.8668 | 0.8668 | MID_BAND | 1.060% |

## BB 詳細（可稽核欄位）

| field | value | note |
|---|---:|---|
| price_usd | 147.7000 | adj_close |
| close_usd | 147.7000 | raw close (for reference) |
| z | 1.4672 | log(price) z-score vs BB mean/stdev |
| pos_in_band | 0.8668 | clipped [0,1] for readability |
| pos_raw | 0.8668 | NOT clipped; can be <0 or >1 when price breaks bands |
| lower_usd | 137.9077 | exp(lower_log) |
| upper_usd | 149.2653 | exp(upper_log) |
| dist_to_lower | 6.630% | (price-lower)/price |
| dist_to_upper | 1.060% | (upper-price)/price |
| band_width | 8.236% | (upper/lower - 1) reading-only |
| bucket | MID_BAND | based on z thresholds |

## forward_mdd（分布解讀）

- 定義：對每一天 t，觀察未來 N 天（t+1..t+N）中的**最低價**相對於當日價的跌幅：min(future)/p0 - 1。
- 理論限制：此值應永遠 <= 0；若 >0，代表對齊/定義錯誤（或資料異常）。
- p5：較穩定的尾部指標（比 min 不那麼容易被單一極端日主宰）。

## FX (USD/TWD)（嚴格同日對齊 + 落後參考值）
- fx_history_parse_status: `OK`
- fx_strict_used_policy: `HISTORY_DATE_MATCH`
- fx_rate_strict (for 2026-02-24): `31.4500`
- derived price_twd (strict): `4645.16`

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
