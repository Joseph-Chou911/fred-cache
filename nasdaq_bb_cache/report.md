# Nasdaq BB Monitor Report (QQQ + VXN)

- report_generated_at_utc: `2026-02-18T07:28:30Z`

## QQQ (PRICE) — BB(60,2) logclose

- snippet.generated_at_utc: `2026-02-18T07:28:30Z`
- data_as_of (meta.max_date): `2026-02-17`  | staleness_days: `1`  | staleness_flag: **`OK`**
- source: `stooq`  | url: `https://stooq.com/q/d/l/?s=qqq.us&i=d`
- action_output: **`NEAR_LOWER_BAND (MONITOR)`**

### Latest

| field | value |
|---|---:|
| date | `2026-02-17` |
| close | `601.3000` |
| bb_mid | `616.4428` |
| bb_lower | `596.6044` |
| bb_upper | `636.9409` |
| z | `-1.5207` |
| trigger_z_le_-2 | `False` |
| distance_to_lower_pct | `0.781%` |
| distance_to_upper_pct | `5.927%` |
| position_in_band | `0.116` |
| bandwidth_pct | `6.54%` |
| bandwidth_delta_pct | `-1.47%` |
| walk_lower_count | 0 |

### Historical simulation (conditional)

- confidence: **`MED`** (sample_size=65 (30-79))

| field | value |
|---|---:|
| metric | `forward_mdd` |
| metric_interpretation | `<=0; closer to 0 is less pain; more negative is deeper drawdown` |
| z_thresh | -2.000000 |
| horizon_days | 20 |
| cooldown_bars | 20 |
| sample_size | 65 |
| p50 | -0.023772 |
| p90 | 0.000000 |
| mean | -0.049430 |
| min | -0.253377 |
| max | 0.000000 |


## VXN (VOL) — BB(60,2) logclose

- snippet.generated_at_utc: `2026-02-18T07:28:30Z`
- data_as_of (meta.max_date): `2026-02-17`  | staleness_days: `1`  | staleness_flag: **`OK`**
- source: `cboe`  | url: `https://cdn.cboe.com/api/global/us_indices/daily_prices/VXN_History.csv`
- selected_source: `cboe` | fallback_used: `False`
- action_output: **`NEAR_UPPER_BAND (WATCH)`**

### Latest

| field | value |
|---|---:|
| date | `2026-02-17` |
| close | `25.9800` |
| bb_mid | `21.4702` |
| bb_lower | `16.3691` |
| bb_upper | `28.1610` |
| z | `1.4057` |
| trigger_z_le_-2 (A_lowvol) | `False` |
| trigger_z_ge_2 (B_highvol) | `False` |
| distance_to_lower_pct | `36.994%` |
| distance_to_upper_pct | `8.395%` |
| position_in_band | `0.815` |
| bandwidth_pct | `54.92%` |
| bandwidth_delta_pct | `-3.80%` |
| walk_upper_count | 0 |
### Historical simulation (conditional)

#### A) Low-Vol / Complacency (z <= threshold)

- confidence: **`LOW`** (sample_size=29 (<30))

| field | value |
|---|---:|
| metric | `forward_max_runup` |
| metric_interpretation | `>=0; larger means bigger spike risk` |
| z_thresh | -2.000000 |
| horizon_days | 20 |
| cooldown_bars | 20 |
| sample_size | 29 |
| p50 | 0.222656 |
| p90 | 0.503378 |
| mean | 0.247371 |
| min | 0.033597 |
| max | 0.766071 |

#### B) High-Vol / Stress (z >= threshold)

- confidence: **`MED`** (sample_size=54 (30-79))

| field | value |
|---|---:|
| metric | `forward_max_runup` |
| metric_interpretation | `>=0; larger means further spike continuation risk` |
| z_thresh | 2.000000 |
| horizon_days | 20 |
| cooldown_bars | 20 |
| sample_size | 54 |
| p50 | 0.095230 |
| p90 | 0.674289 |
| mean | 0.212930 |
| min | 0.000000 |
| max | 1.580728 |


---
Notes:
- `staleness_days` = snippet 的 `generated_at_utc` 日期 − `meta.max_date`；週末/假期可能放大此值。
- PRICE 的 `forward_mdd` 應永遠 `<= 0`（0 代表未回撤）。
- VOL 的 `forward_max_runup` 應永遠 `>= 0`（數值越大代表波動「再爆衝」風險越大）。
- `confidence` 規則：若 `staleness_flag!=OK` 則直接降為 LOW；否則依 sample_size：<30=LOW，30-79=MED，>=80=HIGH。
