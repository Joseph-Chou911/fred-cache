# Bottom Cache Dashboard (v0)

- as_of_ts (TPE): `2026-01-31T23:54:06.356750+08:00`
- run_ts_utc: `2026-01-31T15:54:06.356740Z`
- bottom_state (Global): **NONE**  (streak=6)
- market_cache_as_of_ts: `2026-01-31T04:52:16Z`
- market_cache_generated_at_utc: `2026-01-31T04:52:16Z`

## Rationale (Decision Chain) - Global
- TRIG_PANIC = `0`  (VIX >= 20.0 OR SP500.ret1% <= -1.5)
- TRIG_SYSTEMIC_VETO = `0`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)
- TRIG_REVERSAL = `0`  (panic & NOT systemic & VIX cooling & SP500 stable)
- 因 TRIG_PANIC=0 → 不進入抄底流程（v0 設計）

## Distance to Triggers (How far from activation) - Global
- VIX panic gap = 20.0 - 17.44 = **2.5600**  (<=0 means triggered)
- SP500 ret1% gap = -0.4301902278802939 - (-1.5) = **1.0698**  (<=0 means triggered)
- HYG veto gap (z) = 1.5882991711631762 - (-2.0) = **3.5883**  (<=0 means systemic veto)
- OFR veto gap (z) = (2.0) - -0.0048545895215304025 = **2.0049**  (<=0 means systemic veto)

### Nearest Conditions (Top-2) - Global
- SP500 ret1% gap (<=0 triggered): `1.0698`
- OFR veto gap z (<=0 veto): `2.0049`

## Context (Non-trigger) - Global
- SP500.p252 = `96.0317`; equity_extreme(p252>=95) = `1`
- 註：處於高檔極端時，即使未來出現抄底流程訊號，也應要求更嚴格的反轉確認（僅旁註，不改 triggers）

## Triggers (0/1/NA) - Global
- TRIG_PANIC: `0`
- TRIG_SYSTEMIC_VETO: `0`
- TRIG_REVERSAL: `0`

## TW Local Gate (roll25 + margin)
- tw_state: **TW_BOTTOM_WATCH**  (streak=1)
- UsedDate: `2026-01-30`; run_day_tag: `WEEKEND`; risk_level: `NA`
- Lookback: `20/None`
- margin_signal(TWSE): `NONE`; unit: `億`
- margin_balance(TWSE latest): `3838.9` 億
- margin_chg(TWSE latest): `21.2` 億

### TW Triggers (0/1/NA)
- TRIG_TW_PANIC: `1`  (DownDay & (VolumeAmplified/VolAmplified/NewLow/ConsecutiveBreak))
- TRIG_TW_LEVERAGE_HEAT: `0`  (margin_signal∈{WATCH,ALERT})
- TRIG_TW_REVERSAL: `0`  (PANIC & NOT heat & pct_change>=0 & DownDay=false)

### TW Distances / Gating
- pct_change_to_nonnegative_gap: `-1.452`
- lookback_missing_points: `NA`

### TW Snapshot (key fields)
- pct_change: `-1.452287`; amplitude_pct: `1.692142`; turnover_twd: `941320964545.0`; close: `32063.75`
- signals: DownDay=True, VolumeAmplified=False, VolAmplified=False, NewLow_N=False, ConsecutiveBreak=True

## Action Map (v0)
- Global NONE: 維持既定 DCA/資產配置紀律；不把它當成抄底時點訊號
- Global BOTTOM_WATCH: 只做準備（現金/分批計畫/撤退條件），不進場
- Global BOTTOM_CANDIDATE: 允許分批（例如 2–3 段），但需設定撤退條件
- Global PANIC_BUT_SYSTEMIC: 不抄底，先等信用/壓力解除
- TW Local Gate: 若 TW_BOTTOM_CANDIDATE 才允許把「台股加碼」推進到執行層；否則僅做準備

## Recent History (last 10 buckets)
| tpe_day | as_of_ts | bottom_state | TRIG_PANIC | TRIG_VETO | TRIG_REV | tw_state | tw_panic | tw_heat | tw_rev | note |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---|
| 2026-01-25 | 2026-01-25T19:40:31.851190+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 1 | 0 | equity_extreme |
| 2026-01-26 | 2026-01-26T16:06:45.700719+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 1 | 0 | equity_extreme |
| 2026-01-27 | 2026-01-27T23:58:59.954073+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | None | 0 | equity_extreme |
| 2026-01-29 | 2026-01-29T01:08:17.402179+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 1 | 0 | equity_extreme |
| 2026-01-30 | 2026-01-30T01:25:46.779800+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 1 | 0 | equity_extreme |
| 2026-01-31 | 2026-01-31T23:54:06.356750+08:00 | NONE | 0 | 0 | 0 | TW_BOTTOM_WATCH | 1 | 0 | 0 | equity_extreme |

## Series Snapshot (Global)
| series_id | risk_dir | series_signal | data_date | value | w60.z | w252.p | w60.ret1_pct(%) | w60.z_delta | w60.p_delta |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| VIX | HIGH | NONE | 2026-01-30 | 17.44 | 0.14439227679851765 | 55.158730158730165 | 3.31753554502371 | 0.21106214442730645 | 11.666666666666657 |
| SP500 | LOW | INFO | 2026-01-30 | 6939.03 | 0.9612222920141924 | 96.03174603174604 | -0.4301902278802939 | -0.3242605385950048 | -11.666666666666657 |
| HYG_IEF_RATIO | LOW | NONE | 2026-01-30 | 0.8455284552845529 | 1.5882991711631762 | 79.76190476190477 | 0.173678523160648 | 0.19845450958163124 | 4.999999999999986 |
| OFR_FSI | HIGH | NONE | 2026-01-28 | -2.404 | -0.0048545895215304025 | 21.03174603174603 | -0.8812421317666767 | -0.045013244053773924 | -3.3333333333333286 |

## Data Sources
- Global (single-source): `market_cache/stats_latest.json`
- TW Local Gate (existing workflow outputs, no fetch):
  - `roll25_cache/latest_report.json`
  - `taiwan_margin_cache/latest.json`  (unit: 億)
- This dashboard does not fetch external URLs directly.
