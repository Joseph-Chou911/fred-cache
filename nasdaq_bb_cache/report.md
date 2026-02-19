# Nasdaq BB Monitor Report (QQQ + VXN)

- report_generated_at_utc: `2026-02-19T15:30:42Z`

## 15秒摘要

- **QQQ** (2026-02-19 close=604.1500) → **NORMAL_RANGE** (reason=default); dist_to_lower=0.899%; dist_to_upper=5.198%; 20D forward_mdd: p50=-3.28%, p10=-14.48%, min=-24.99% (conf=HIGH)
- **VXN** (2026-02-18 close=24.9600) → **NORMAL_RANGE** (reason=default); z=1.1702; pos=0.747; bwΔ=-3.51%; High-Vol tail (B) p90 runup=67.4% (n=54) (conf=MED)


## QQQ (PRICE) — BB(60,2) logclose

- snippet.generated_at_utc: `2026-02-19T15:30:41Z`
- data_as_of (meta.max_date): `2026-02-19`  | staleness_days: `0`  | staleness_flag: **`OK`**
- source: `stooq`  | url: `https://stooq.com/q/d/l/?s=qqq.us&i=d`
- action_output: **`NORMAL_RANGE`**
- trigger_reason: `default`

### Latest

| field | value |
|---|---:|
| date | `2026-02-19` |
| close | `604.1500` |
| bb_mid | `616.8630` |
| bb_lower | `598.7206` |
| bb_upper | `635.5553` |
| z | `-1.3952` |
| trigger_z_le_-2 | `False` |
| distance_to_lower_pct | `0.899%` |
| distance_to_upper_pct | `5.198%` |
| position_in_band | `0.147` |
| bandwidth_pct | `5.97%` |
| bandwidth_delta_pct | `-7.46%` |
| walk_lower_count | 0 |

### Historical simulation (conditional)

- confidence: **`HIGH`** (sample_size=87 (>=80))

| field | value |
|---|---:|
| metric | `forward_mdd` |
| metric_interpretation | `<=0; closer to 0 is less pain; more negative is deeper drawdown` |
| z_thresh | -1.500000 |
| horizon_days | 20 |
| cooldown_bars | 20 |
| sample_size | 87 |
| p10 | -0.144813 |
| p50 | -0.032842 |
| p90 | 0.000000 |
| mean | -0.054391 |
| min | -0.249947 |
| max | 0.000000 |
| gate | `{'field': 'z', 'op': '<=', 'value': -1.5}` |
| condition | `{'field': 'z', 'op': '<=', 'value': -1.5}` |


## VXN (VOL) — BB(60,2) logclose

- snippet.generated_at_utc: `2026-02-19T15:30:42Z`
- data_as_of (meta.max_date): `2026-02-18`  | staleness_days: `1`  | staleness_flag: **`OK`**
- source: `cboe`  | url: `https://cdn.cboe.com/api/global/us_indices/daily_prices/VXN_History.csv`
- selected_source: `cboe` | fallback_used: `False`
- action_output: **`NORMAL_RANGE`**
- trigger_reason: `default`

### Latest

| field | value |
|---|---:|
| date | `2026-02-18` |
| close | `24.9600` |
| bb_mid | `21.4129` |
| bb_lower | `16.4780` |
| bb_upper | `27.8258` |
| z | `1.1702` |
| trigger_z_le_-2 (A_lowvol) | `False` |
| trigger_z_ge_2 (B_highvol) | `False` |
| distance_to_lower_pct | `33.982%` |
| distance_to_upper_pct | `11.481%` |
| position_in_band | `0.747` |
| bandwidth_pct | `52.99%` |
| bandwidth_delta_pct | `-3.51%` |
| walk_upper_count | 0 |
### Historical simulation (conditional)

#### C) Position-based WATCH (pos >= threshold)

- confidence: **`MED`** (sample_size=78 (30-79))

| field | value |
|---|---:|
| metric | `forward_max_runup` |
| metric_interpretation | `>=0; larger means further spike continuation risk` |
| z_thresh | `NA` |
| horizon_days | 20 |
| cooldown_bars | 20 |
| sample_size | 78 |
| p10 | 0.000000 |
| p50 | 0.111346 |
| p90 | 0.581213 |
| mean | 0.205903 |
| min | 0.000000 |
| max | 1.739651 |
| gate | `{'field': 'position_in_band', 'op': '>=', 'value': 0.8}` |
| condition | `{'field': 'position_in_band', 'op': '>=', 'value': 0.8}` |

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
| p10 | 0.049227 |
| p50 | 0.222656 |
| p90 | 0.503378 |
| mean | 0.247371 |
| min | 0.033597 |
| max | 0.766071 |
| gate | `{'field': 'z', 'op': '<=', 'value': -2.0}` |
| condition | `{'field': 'z', 'op': '<=', 'value': -2.0}` |

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
| p10 | 0.000000 |
| p50 | 0.095230 |
| p90 | 0.674289 |
| mean | 0.212930 |
| min | 0.000000 |
| max | 1.580728 |
| gate | `{'field': 'z', 'op': '>=', 'value': 2.0}` |
| condition | `{'field': 'z', 'op': '>=', 'value': 2.0}` |


---
Notes:
- `staleness_days` = snippet 的 `generated_at_utc` 日期 − `meta.max_date`；週末/假期可能放大此值。
- PRICE 的 `forward_mdd` 應永遠 `<= 0`（0 代表未回撤）。
- VOL 的 `forward_max_runup` 應永遠 `>= 0`（數值越大代表波動「再爆衝」風險越大）。
- `confidence` 規則：若 `staleness_flag!=OK` 則直接降為 LOW；否則依 sample_size：<30=LOW，30-79=MED，>=80=HIGH。
- `trigger_reason` 用於稽核 action_output 被哪條規則觸發。
