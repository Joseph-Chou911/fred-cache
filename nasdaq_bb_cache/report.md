# Nasdaq BB Monitor Report (QQQ + VXN)

- report_generated_at_utc: `2026-02-18T04:38:28Z`

## QQQ (PRICE) — BB(60,2) logclose

- snippet.generated_at_utc: `2026-02-18T04:38:27Z`
- data_as_of (meta.max_date): `2026-02-17`  | staleness_days: `1`  | staleness_flag: **`OK`**
- source: `stooq`  | url: `https://stooq.com/q/d/l/?s=qqq.us&i=d`
- action_output: **`NEAR_LOWER_BAND (MONITOR)`**

### Latest

| field | value |
|---|---:|
| date | `2026-02-17` |
| close | 601.3000 |
| bb_mid | 616.4428 |
| bb_lower | 596.6044 |
| bb_upper | 636.9409 |
| z | -1.5207 |
| trigger_z_le_-2 | `False` |
| distance_to_lower_pct | 0.787% |
| position_in_band | 0.116 |
| bandwidth_pct | 6.54% |
| bandwidth_delta_pct | -1.47% |
| walk_count | 0 |

### Historical simulation (conditional)

| field | value |
|---|---:|
| metric | `forward_mdd` |
| metric_interpretation | `<=0; closer to 0 is less pain; more negative is deeper drawdown` |
| z_thresh | -2.0 |
| horizon_days | 20 |
| cooldown_bars | 20 |
| sample_size | 65 |
| p50 | -0.023772 |
| p90 | 0.000000 |
| mean | -0.049430 |
| min | -0.253377 |
| max | 0.000000 |

## VXN (VOL) — BB(60,2) logclose

- snippet.generated_at_utc: `2026-02-18T04:38:27Z`
- data_as_of (meta.max_date): `2026-02-13`  | staleness_days: `5`  | staleness_flag: **`HIGH`**
- source: `fred`  | url: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=VXNCLS`
- action_output: **`NORMAL_RANGE`**

### Latest

| field | value |
|---|---:|
| date | `2026-02-13` |
| close | 26.3700 |
| bb_mid | 21.5278 |
| bb_lower | 16.2423 |
| bb_upper | 28.5332 |
| z | 1.4403 |
| trigger_z_le_-2 | `False` |
| distance_to_lower_pct | 62.353% |
| position_in_band | 0.824 |
| bandwidth_pct | 57.09% |
| bandwidth_delta_pct | -1.31% |
| walk_count | 0 |

> ⚠️ VXN data is stale (lag > 2 days). Treat VOL-based interpretation as lower confidence.

### Historical simulation (conditional)

| field | value |
|---|---:|
| metric | `forward_max_runup` |
| metric_interpretation | `>=0; larger means bigger vol spike risk` |
| z_thresh | -2.0 |
| horizon_days | 20 |
| cooldown_bars | 20 |
| sample_size | 59 |
| p50 | 0.170914 |
| p90 | 0.442227 |
| mean | 0.212497 |
| min | 0.000000 |
| max | 0.766071 |

---
Notes:
- `staleness_days` 以 snippet 的 `generated_at_utc` 日期減 `meta.max_date` 計算；週末/假期可能放大此值。
- PRICE 的 `historical_simulation.metric=forward_mdd` 應永遠 `<= 0`（0 代表未回撤）。
- VXN 的 `historical_simulation.metric=forward_max_runup` 應永遠 `>= 0`（數值越大代表波動爆衝風險越大）。
