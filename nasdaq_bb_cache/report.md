# Nasdaq BB Monitor Report (QQQ + VXN)

- report_generated_at_utc: `2026-02-23T01:52:18Z`

## 15秒摘要

- **QQQ** (2026-02-20 close=608.8100) → **NORMAL_RANGE** (reason=default); dist_to_lower=1.407%; dist_to_upper=4.232%; 20D forward_mdd: p50=-3.28%, p10=-14.48%, min=-24.99% (conf=LOW)
- **VXN** (2026-02-20 close=24.2300) → **NORMAL_RANGE** (reason=default); z=1.1288; pos=0.741; bwΔ=-4.59%; High-Vol tail (B) p90 runup=67.4% (n=54) (conf=LOW)


## QQQ (PRICE) — BB(60,2) logclose

- snippet.generated_at_utc: `2026-02-23T01:52:17Z`
- data_as_of (meta.max_date): `2026-02-20`  | staleness_days: `3`  | staleness_flag: **`HIGH`**
- source: `stooq`  | url: `https://stooq.com/q/d/l/?s=qqq.us&i=d`
- action_output: **`NORMAL_RANGE`**
- trigger_reason: `default`

### Latest

| field | value |
|---|---:|
| date | `2026-02-20` |
| close | `608.8100` |
| bb_mid | `617.1730` |
| bb_lower | `600.2458` |
| bb_upper | `634.5775` |
| z | `-0.9812` |
| trigger_z_le_-2 | `False` |
| distance_to_lower_pct | `1.407%` |
| distance_to_upper_pct | `4.232%` |
| position_in_band | `0.249` |
| bandwidth_pct | `5.56%` |
| bandwidth_delta_pct | `-7.01%` |
| walk_lower_count | 0 |

### Historical simulation (conditional)

- confidence: **`LOW`** (staleness_flag=HIGH)

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

- snippet.generated_at_utc: `2026-02-23T01:52:18Z`
- data_as_of (meta.max_date): `2026-02-20`  | staleness_days: `3`  | staleness_flag: **`HIGH`**
- source: `cboe`  | url: `https://cdn.cboe.com/api/global/us_indices/daily_prices/VXN_History.csv`
- selected_source: `cboe` | fallback_used: `False`
- action_output: **`NORMAL_RANGE`**
- trigger_reason: `default`

### Latest

| field | value |
|---|---:|
| date | `2026-02-20` |
| close | `24.2300` |
| bb_mid | `21.2629` |
| bb_lower | `16.8698` |
| bb_upper | `26.8000` |
| z | `1.1288` |
| trigger_z_le_-2 (A_lowvol) | `False` |
| trigger_z_ge_2 (B_highvol) | `False` |
| distance_to_lower_pct | `30.376%` |
| distance_to_upper_pct | `10.607%` |
| position_in_band | `0.741` |
| bandwidth_pct | `46.70%` |
| bandwidth_delta_pct | `-4.59%` |
| walk_upper_count | 0 |
### Historical simulation (conditional)

#### C) Position-based WATCH (pos >= threshold)

- confidence: **`LOW`** (staleness_flag=HIGH)

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

- confidence: **`LOW`** (staleness_flag=HIGH)

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

- confidence: **`LOW`** (staleness_flag=HIGH)

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
