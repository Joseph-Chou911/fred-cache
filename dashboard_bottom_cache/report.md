# Bottom Cache Dashboard (v0.1)

- renderer_version: `v0.1.10`
- as_of_ts (TPE): `2026-03-13T00:32:11.552603+08:00`
- run_ts_utc: `2026-03-12T16:32:11.552579Z`
- bottom_state (Global): **PANIC_BUT_SYSTEMIC**  (streak=9)
- market_cache_as_of_ts: `2026-03-12T03:18:55Z`
- market_cache_generated_at_utc: `2026-03-12T03:18:55Z`
- history_load_status: `OK`; reason: `dict.items`; loaded_items: `34`
- history_pre_items: `34`; history_post_items: `35`; pre_unique_days: `34`; post_unique_days: `35`
- history_write: status=`OK`; reason=`ok`; allow_reset=`False`; allow_shrink=`False`
- history_backup: status=`OK`; reason=`copied_pre_write`; file=`dashboard_bottom_cache/history.json.bak.20260312T163211Z.json`; bytes=`31725`; keep_n=`30`; prune_deleted=`1`

## Rationale (Decision Chain) - Global
- TRIG_PANIC = `1`  (VIX >= 20.0 OR SP500.ret1% <= -1.5)
- TRIG_SYSTEMIC_VETO = `1`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)
- TRIG_REVERSAL = `0`  (panic & NOT systemic & VIX cooling & SP500 stable)

## Distance to Triggers - Global
- VIX panic gap: `-4.2300`
- SP500 ret1% gap: `1.4162`
- HYG veto gap(z): `1.1084`
- OFR veto gap(z): `-2.4251`

## Context (Non-trigger) - Global
- SP500.p252: `69.04761904761905`; equity_extreme(p252>=95): `0`

## TW Local Gate (roll25 + margin)
- tw_state: **NONE**  (streak=35)
- UsedDate: `2026-03-11`; run_day_tag: `WEEKDAY`; used_date_status: `DATA_NOT_UPDATED`
- Lookback: `20/20`
- roll25_raw: DownDay=`False`; VolumeAmplified=`False`; VolAmplified=`False`; NewLow_N=`0`; ConsecutiveBreak=`0`
- roll25_paired_basis: `False` (basis = VolumeAmplified OR VolAmplified OR (NewLow_N>=1))
- margin_final_signal(TWSE): `NONE`; confidence: `DOWNGRADED`; unit: `億`
- margin_balance(TWSE latest): `3793.7` 億
- margin_chg(TWSE latest): `32.2` 億
- margin_flow_audit: signal=`NONE`; sum_last5=`2.1`; pos_days_last5=`3`
- margin_level_gate_audit: gate=`NA`; points=`30/60`; p=`NA`; p_min=`95.0`
- tw_panic_hit: `DownDay=False + Stress={}; Miss={VolumeAmplified,VolAmplified,NewLow_N>=1,ConsecutiveBreak>=2&paired}`

### TW Triggers (0/1/NA)
- TRIG_TW_PANIC: `0`
- TRIG_TW_LEVERAGE_HEAT: `0`
- TRIG_TW_REVERSAL: `0`

## Recent History (last 10 buckets)
| tpe_day | as_of_ts | bottom_state | TRIG_PANIC | TRIG_VETO | TRIG_REV | tw_state | tw_panic | tw_heat | tw_rev | margin_final | margin_conf |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|
| 2026-03-02 | 2026-03-02T23:58:33.203588+08:00 | NONE | 0 | 1 | 0 | NONE | 0 | 1 | 0 | ALERT | DOWNGRADED |
| 2026-03-04 | 2026-03-04T00:04:35.301270+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 1 | 0 | WATCH | DOWNGRADED |
| 2026-03-05 | 2026-03-05T00:00:21.791540+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-03-06 | 2026-03-06T23:56:26.230083+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-03-07 | 2026-03-07T23:41:21.273825+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-03-08 | 2026-03-08T23:42:24.283007+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-03-10 | 2026-03-10T00:30:16.829140+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-03-11 | 2026-03-11T00:30:47.201420+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-03-12 | 2026-03-12T00:07:22.009328+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-03-13 | 2026-03-13T00:32:11.552603+08:00 | PANIC_BUT_SYSTEMIC | 1 | 1 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |

## Data Sources
- Global (single-source): `market_cache/stats_latest.json`
- TW Local Gate (existing workflow outputs, no fetch):
  - `roll25_cache/latest_report.json`
  - `taiwan_margin_cache/latest.json`
- This dashboard does not fetch external URLs directly.
