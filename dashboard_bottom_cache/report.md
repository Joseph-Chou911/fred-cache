# Bottom Cache Dashboard (v0.1)

- as_of_ts (TPE): `2026-02-01T15:36:43.137391+08:00`
- run_ts_utc: `2026-02-01T07:36:43.137366Z`
- bottom_state (Global): **NONE**  (streak=7)
- market_cache_as_of_ts: `2026-02-01T05:39:45Z`
- market_cache_generated_at_utc: `2026-02-01T05:39:45Z`

## Rationale (Decision Chain) - Global
- TRIG_PANIC = `0`  (VIX >= 20.0 OR SP500.ret1% <= -1.5)
- TRIG_SYSTEMIC_VETO = `0`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)
- TRIG_REVERSAL = `0`  (panic & NOT systemic & VIX cooling & SP500 stable)

## Distance to Triggers - Global
- VIX panic gap: `2.5600`
- SP500 ret1% gap: `1.0698`
- HYG veto gap(z): `3.5883`
- OFR veto gap(z): `2.0049`

## Context (Non-trigger) - Global
- SP500.p252: `96.03174603174604`; equity_extreme(p252>=95): `1`

## TW Local Gate (roll25 + margin)
- tw_state: **TW_BOTTOM_WATCH**  (streak=2)
- UsedDate: `2026-01-30`; run_day_tag: `WEEKEND`; used_date_status: `OK_LATEST`
- Lookback: `20/20`
- margin_final_signal(TWSE): `NA`; confidence: `DOWNGRADED`; unit: `億`
- margin_balance(TWSE latest): `3838.9` 億
- margin_chg(TWSE latest): `21.2` 億

### TW Triggers (0/1/NA)
- TRIG_TW_PANIC: `1`
- TRIG_TW_LEVERAGE_HEAT: `0`
- TRIG_TW_REVERSAL: `0`

### TW Distances / Gating
- pct_change_to_nonnegative_gap: `1.452`
- lookback_missing_points: `0`

### TW Snapshot (key fields)
- pct_change: `-1.452287`; amplitude_pct: `1.692142`; turnover_twd: `941320964545.0`; close: `32063.75`
- signals: DownDay=True, VolumeAmplified=False, VolAmplified=False, NewLow_N=0, ConsecutiveBreak=2
- stress_flags: newlow=False, consecutive_break>=2=True

## Recent History (last 10 buckets)
| tpe_day | as_of_ts | bottom_state | TRIG_PANIC | TRIG_VETO | TRIG_REV | tw_state | tw_panic | tw_heat | tw_rev |
|---|---|---|---:|---:|---:|---|---:|---:|---:|
| 2026-01-25 | 2026-01-25T19:40:31.851190+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 1 | 0 |
| 2026-01-26 | 2026-01-26T16:06:45.700719+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 1 | 0 |
| 2026-01-27 | 2026-01-27T23:58:59.954073+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | NA | 0 |
| 2026-01-29 | 2026-01-29T01:08:17.402179+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 1 | 0 |
| 2026-01-30 | 2026-01-30T01:25:46.779800+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 1 | 0 |
| 2026-01-31 | 2026-01-31T23:54:06.356750+08:00 | NONE | 0 | 0 | 0 | TW_BOTTOM_WATCH | 1 | 0 | 0 |
| 2026-02-01 | 2026-02-01T15:36:43.137391+08:00 | NONE | 0 | 0 | 0 | TW_BOTTOM_WATCH | 1 | 0 | 0 |

## Series Snapshot (Global)
| series_id | risk_dir | series_signal | data_date | value | w60.z | w252.p | w60.ret1_pct(%) |
|---|---|---|---|---:|---:|---:|---:|
| VIX | HIGH | NONE | 2026-01-30 | 17.44 | 0.14439227679851765 | 55.158730158730165 | 3.31753554502371 |
| SP500 | LOW | INFO | 2026-01-30 | 6939.03 | 0.9612222920141924 | 96.03174603174604 | -0.4301902278802939 |
| HYG_IEF_RATIO | LOW | NONE | 2026-01-30 | 0.8455284552845529 | 1.5882991711631762 | 79.76190476190477 | 0.173678523160648 |
| OFR_FSI | HIGH | NONE | 2026-01-28 | -2.404 | -0.0048545895215304025 | 21.03174603174603 | -0.8812421317666767 |

## Data Sources
- Global (single-source): `market_cache/stats_latest.json`
- TW Local Gate (existing workflow outputs, no fetch):
  - `roll25_cache/latest_report.json`
  - `taiwan_margin_cache/latest.json`
- This dashboard does not fetch external URLs directly.
