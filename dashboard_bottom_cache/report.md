# Bottom Cache Dashboard (v0.1)

- renderer_version: `v0.1.10`
- as_of_ts (TPE): `2026-03-10T00:30:16.829140+08:00`
- run_ts_utc: `2026-03-09T16:30:16.829122Z`
- bottom_state (Global): **PANIC_BUT_SYSTEMIC**  (streak=6)
- market_cache_as_of_ts: `2026-03-09T03:22:08Z`
- market_cache_generated_at_utc: `2026-03-09T03:22:08Z`
- history_load_status: `OK`; reason: `dict.items`; loaded_items: `31`
- history_pre_items: `31`; history_post_items: `32`; pre_unique_days: `31`; post_unique_days: `32`
- history_write: status=`OK`; reason=`ok`; allow_reset=`False`; allow_shrink=`False`
- history_backup: status=`OK`; reason=`copied_pre_write`; file=`dashboard_bottom_cache/history.json.bak.20260309T163016Z.json`; bytes=`28923`; keep_n=`30`; prune_deleted=`1`

## Rationale (Decision Chain) - Global
- TRIG_PANIC = `1`  (VIX >= 20.0 OR SP500.ret1% <= -1.5)
- TRIG_SYSTEMIC_VETO = `1`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)
- TRIG_REVERSAL = `0`  (panic & NOT systemic & VIX cooling & SP500 stable)

## Distance to Triggers - Global
- VIX panic gap: `-9.4900`
- SP500 ret1% gap: `0.1723`
- HYG veto gap(z): `0.0507`
- OFR veto gap(z): `-2.1683`

## Context (Non-trigger) - Global
- SP500.p252: `67.85714285714286`; equity_extreme(p252>=95): `0`

## TW Local Gate (roll25 + margin)
- tw_state: **NONE**  (streak=32)
- UsedDate: `2026-03-06`; run_day_tag: `WEEKDAY`; used_date_status: `DATA_NOT_UPDATED`
- Lookback: `20/20`
- roll25_raw: DownDay=`True`; VolumeAmplified=`False`; VolAmplified=`False`; NewLow_N=`0`; ConsecutiveBreak=`1`
- roll25_paired_basis: `False` (basis = VolumeAmplified OR VolAmplified OR (NewLow_N>=1))
- margin_final_signal(TWSE): `NONE`; confidence: `DOWNGRADED`; unit: `億`
- margin_balance(TWSE latest): `3719.6` 億
- margin_chg(TWSE latest): `-107.2` 億
- margin_flow_audit: signal=`NONE`; sum_last5=`-195.5`; pos_days_last5=`2`
- margin_level_gate_audit: gate=`NA`; points=`30/60`; p=`NA`; p_min=`95.0`
- tw_panic_hit: `DownDay=True + Stress={}; Miss={VolumeAmplified,VolAmplified,NewLow_N>=1,ConsecutiveBreak>=2&paired}`

### TW Triggers (0/1/NA)
- TRIG_TW_PANIC: `0`
- TRIG_TW_LEVERAGE_HEAT: `0`
- TRIG_TW_REVERSAL: `0`

## Recent History (last 10 buckets)
| tpe_day | as_of_ts | bottom_state | TRIG_PANIC | TRIG_VETO | TRIG_REV | tw_state | tw_panic | tw_heat | tw_rev | margin_final | margin_conf |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|
| 2026-02-27 | 2026-02-27T23:55:12.066505+08:00 | NONE | 0 | 1 | 0 | NONE | 0 | 1 | 0 | ALERT | DOWNGRADED |
| 2026-02-28 | 2026-02-28T23:40:26.856407+08:00 | NONE | 0 | 1 | 0 | NONE | 0 | 1 | 0 | ALERT | DOWNGRADED |
| 2026-03-01 | 2026-03-01T23:41:36.319543+08:00 | NONE | 0 | 1 | 0 | NONE | 0 | 1 | 0 | ALERT | DOWNGRADED |
| 2026-03-02 | 2026-03-02T23:58:33.203588+08:00 | NONE | 0 | 1 | 0 | NONE | 0 | 1 | 0 | ALERT | DOWNGRADED |
| 2026-03-04 | 2026-03-04T00:04:35.301270+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 1 | 0 | WATCH | DOWNGRADED |
| 2026-03-05 | 2026-03-05T00:00:21.791540+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-03-06 | 2026-03-06T23:56:26.230083+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-03-07 | 2026-03-07T23:41:21.273825+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-03-08 | 2026-03-08T23:42:24.283007+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-03-10 | 2026-03-10T00:30:16.829140+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |

## Data Sources
- Global (single-source): `market_cache/stats_latest.json`
- TW Local Gate (existing workflow outputs, no fetch):
  - `roll25_cache/latest_report.json`
  - `taiwan_margin_cache/latest.json`
- This dashboard does not fetch external URLs directly.
