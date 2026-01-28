# Bottom Cache Dashboard (v0)

- as_of_ts (TPE): `2026-01-29T01:08:17.402179+08:00`
- run_ts_utc: `2026-01-28T17:08:17.402164Z`
- bottom_state (Global): **NONE**  (streak=4)
- market_cache_as_of_ts: `2026-01-28T04:15:06Z`
- market_cache_generated_at_utc: `2026-01-28T04:15:06Z`

## Rationale (Decision Chain) - Global
- TRIG_PANIC = `0`  (VIX >= 20.0 OR SP500.ret1% <= -1.5)
- TRIG_SYSTEMIC_VETO = `0`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)
- TRIG_REVERSAL = `0`  (panic & NOT systemic & VIX cooling & SP500 stable)
- 因 TRIG_PANIC=0 → 不進入抄底流程（v0 設計）

## Distance to Triggers (How far from activation) - Global
- VIX panic gap = 20.0 - 16.35 = **3.6500**  (<=0 means triggered)
- SP500 ret1% gap = 0.40818793047137725 - (-1.5) = **1.9082**  (<=0 means triggered)
- HYG veto gap (z) = 1.8112587337684396 - (-2.0) = **3.8113**  (<=0 means systemic veto)
- OFR veto gap (z) = (2.0) - -0.3164845128042814 = **2.3165**  (<=0 means systemic veto)

### Nearest Conditions (Top-2) - Global
- SP500 ret1% gap (<=0 triggered): `1.9082`
- OFR veto gap z (<=0 veto): `2.3165`

## Context (Non-trigger) - Global
- SP500.p252 = `100.0000`; equity_extreme(p252>=95) = `1`
- 註：處於高檔極端時，即使未來出現抄底流程訊號，也應要求更嚴格的反轉確認（僅旁註，不改 triggers）

## Triggers (0/1/NA) - Global
- TRIG_PANIC: `0`
- TRIG_SYSTEMIC_VETO: `0`
- TRIG_REVERSAL: `0`

## TW Local Gate (roll25 + margin)
- tw_state: **NONE**  (streak=4)
- UsedDate: `2026-01-27`; run_day_tag: `WEEKDAY`; risk_level: `NA`
- Lookback: `20/None`
- margin_signal(TWSE): `ALERT`; unit: `億`
- margin_balance(TWSE latest): `3849.2` 億
- margin_chg(TWSE latest): `21.9` 億

### TW Triggers (0/1/NA)
- TRIG_TW_PANIC: `0`  (DownDay & (VolumeAmplified/VolAmplified/NewLow/ConsecutiveBreak))
- TRIG_TW_LEVERAGE_HEAT: `1`  (margin_signal∈{WATCH,ALERT})
- TRIG_TW_REVERSAL: `0`  (PANIC & NOT heat & pct_change>=0 & DownDay=false)

### TW Distances / Gating
- pct_change_to_nonnegative_gap: `0.790`
- lookback_missing_points: `NA`

### TW Snapshot (key fields)
- pct_change: `0.790282`; amplitude_pct: `1.038812`; turnover_twd: `817604546187.0`; close: `32317.92`
- signals: DownDay=False, VolumeAmplified=False, VolAmplified=False, NewLow_N=False, ConsecutiveBreak=False

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

## Series Snapshot (Global)
| series_id | risk_dir | series_signal | data_date | value | w60.z | w252.p | w60.ret1_pct(%) | w60.z_delta | w60.p_delta |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| VIX | HIGH | NONE | 2026-01-27 | 16.35 | -0.28013511159805987 | 33.730158730158735 | 1.2383900928792748 | 0.08072120107107777 | 3.3333333333333357 |
| SP500 | LOW | INFO | 2026-01-27 | 6978.6 | 1.4754457981165812 | 100.0 | 0.40818793047137725 | 0.2605903091858359 | 5.0 |
| HYG_IEF_RATIO | LOW | NONE | 2026-01-27 | 0.8456970202125442 | 1.8112587337684396 | 79.76190476190477 | 0.10227478716848093 | 0.07936709215021787 | 3.333333333333343 |
| OFR_FSI | HIGH | NONE | 2026-01-23 | -2.505 | -0.3164845128042814 | 11.11111111111111 | 6.529850746268666 | 0.49720671423638535 | 11.666666666666671 |

## Data Sources
- Global (single-source): `market_cache/stats_latest.json`
- TW Local Gate (existing workflow outputs, no fetch):
  - `roll25_cache/latest_report.json`
  - `taiwan_margin_cache/latest.json`  (unit: 億)
- This dashboard does not fetch external URLs directly.
