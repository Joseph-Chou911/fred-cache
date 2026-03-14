# Nasdaq BB Monitor Report (QQQ + VXN)

- report_generated_at_utc: `2026-03-14T00:40:09Z`

## 15秒摘要

- **QQQ** (2026-03-13 close=593.7200) → **LOWER_BAND_TOUCH (MONITOR / SCALE_IN_ONLY)** (reason=z<=-2); dist_to_lower=-0.224%; dist_to_upper=6.651%; 20D forward_mdd: p50=-3.18%, p10=-14.47%, min=-24.99% (conf=HIGH)
- **VXN** (2026-03-13 close=29.8700) → **NEAR_UPPER_BAND (WATCH)** (reason=position_in_band>=0.8 (pos=0.960)); z=1.8792; pos=0.960; bwΔ=2.98%; Pos-WATCH (C) p90 runup=58.0% (n=79) (conf=MED)


## QQQ (PRICE) — BB(60,2) logclose

- snippet.generated_at_utc: `2026-03-14T00:40:08Z`
- data_as_of (meta.max_date): `2026-03-13`  | staleness_days: `1`  | staleness_flag: **`OK`**
- source: `stooq`  | url: `https://stooq.com/q/d/l/?s=qqq.us&i=d`
- action_output: **`LOWER_BAND_TOUCH (MONITOR / SCALE_IN_ONLY)`**
- trigger_reason: `z<=-2`

### Latest

| field | value |
|---|---:|
| date | `2026-03-13` |
| close | `593.7200` |
| bb_mid | `613.8331` |
| bb_lower | `595.0501` |
| bb_upper | `633.2090` |
| z | `-2.1440` |
| trigger_z_le_-2 | `True` |
| distance_to_lower_pct | `-0.224%` |
| distance_to_upper_pct | `6.651%` |
| position_in_band | `0.000` |
| bandwidth_pct | `6.22%` |
| bandwidth_delta_pct | `4.01%` |
| walk_lower_count | 1 |

### Historical simulation (conditional)

- confidence: **`HIGH`** (sample_size=88 (>=80))

| field | value |
|---|---:|
| metric | `forward_mdd` |
| metric_interpretation | `<=0; closer to 0 is less pain; more negative is deeper drawdown` |
| z_thresh | -1.500000 |
| horizon_days | 20 |
| cooldown_bars | 20 |
| sample_size | 88 |
| p10 | -0.144695 |
| p50 | -0.031846 |
| p90 | 0.000000 |
| mean | -0.053889 |
| min | -0.249947 |
| max | 0.000000 |
| gate | `{'field': 'z', 'op': '<=', 'value': -1.5}` |
| condition | `{'field': 'z', 'op': '<=', 'value': -1.5}` |


## VXN (VOL) — BB(60,2) logclose

- snippet.generated_at_utc: `2026-03-14T00:40:08Z`
- data_as_of (meta.max_date): `2026-03-13`  | staleness_days: `1`  | staleness_flag: **`OK`**
- source: `cboe`  | url: `https://cdn.cboe.com/api/global/us_indices/daily_prices/VXN_History.csv`
- selected_source: `cboe` | fallback_used: `False`
- action_output: **`NEAR_UPPER_BAND (WATCH)`**
- trigger_reason: `position_in_band>=0.8 (pos=0.960)`

### Latest

| field | value |
|---|---:|
| date | `2026-03-13` |
| close | `29.8700` |
| bb_mid | `22.5106` |
| bb_lower | `16.6587` |
| bb_upper | `30.4181` |
| z | `1.8792` |
| trigger_z_le_-2 (A_lowvol) | `False` |
| trigger_z_ge_2 (B_highvol) | `False` |
| distance_to_lower_pct | `44.229%` |
| distance_to_upper_pct | `1.835%` |
| position_in_band | `0.960` |
| bandwidth_pct | `61.12%` |
| bandwidth_delta_pct | `2.98%` |
| walk_upper_count | 0 |
### Historical simulation (conditional)

#### C) Position-based WATCH (pos >= threshold)

- confidence: **`MED`** (sample_size=79 (30-79))

| field | value |
|---|---:|
| metric | `forward_max_runup` |
| metric_interpretation | `>=0; larger means further spike continuation risk` |
| z_thresh | `NA` |
| horizon_days | 20 |
| cooldown_bars | 20 |
| sample_size | 79 |
| p10 | 0.000000 |
| p50 | 0.118143 |
| p90 | 0.580152 |
| mean | 0.206843 |
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
| p10 | 0.045259 |
| p50 | 0.163388 |
| p90 | 0.451860 |
| mean | 0.230673 |
| min | 0.014123 |
| max | 0.760994 |
| gate | `{'field': 'z', 'op': '<=', 'value': -2.0}` |
| condition | `{'field': 'z', 'op': '<=', 'value': -2.0}` |

#### B) High-Vol / Stress (z >= threshold)

- confidence: **`MED`** (sample_size=55 (30-79))

| field | value |
|---|---:|
| metric | `forward_max_runup` |
| metric_interpretation | `>=0; larger means further spike continuation risk` |
| z_thresh | 2.000000 |
| horizon_days | 20 |
| cooldown_bars | 20 |
| sample_size | 55 |
| p10 | 0.000000 |
| p50 | 0.097802 |
| p90 | 0.660538 |
| mean | 0.213107 |
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
