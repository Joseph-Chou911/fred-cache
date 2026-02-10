# Bottom Cache Dashboard (v0.1)

- renderer_version: `v0.1.10`
- as_of_ts (TPE): `2026-02-11T00:34:43.635609+08:00`
- run_ts_utc: `2026-02-10T16:34:43.635598Z`
- bottom_state (Global): **NONE**  (streak=9)
- market_cache_as_of_ts: `2026-02-10T04:42:44Z`
- market_cache_generated_at_utc: `2026-02-10T04:42:44Z`
- history_load_status: `OK`; reason: `dict.items`; loaded_items: `8`
- history_pre_items: `8`; history_post_items: `9`; pre_unique_days: `8`; post_unique_days: `9`
- history_write: status=`OK`; reason=`ok`; allow_reset=`False`; allow_shrink=`False`
- history_backup: status=`OK`; reason=`copied_pre_write`; file=`dashboard_bottom_cache/history.json.bak.20260210T163443Z.json`; bytes=`7438`; keep_n=`30`; prune_deleted=`0`

## Rationale (Decision Chain) - Global
- TRIG_PANIC = `0`  (VIX >= 20.0 OR SP500.ret1% <= -1.5)
- TRIG_SYSTEMIC_VETO = `0`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)
- TRIG_REVERSAL = `0`  (panic & NOT systemic & VIX cooling & SP500 stable)

## Distance to Triggers - Global
- VIX panic gap: `2.6400`
- SP500 ret1% gap: `1.9691`
- HYG veto gap(z): `2.7821`
- OFR veto gap(z): `0.6264`

## Context (Non-trigger) - Global
- SP500.p252: `97.61904761904762`; equity_extreme(p252>=95): `1`

## TW Local Gate (roll25 + margin)
- tw_state: **NONE**  (streak=9)
- UsedDate: `2026-02-09`; run_day_tag: `WEEKDAY`; used_date_status: `DATA_NOT_UPDATED`
- Lookback: `20/20`
- roll25_raw: DownDay=`False`; VolumeAmplified=`False`; VolAmplified=`False`; NewLow_N=`0`; ConsecutiveBreak=`0`
- roll25_paired_basis: `False` (basis = VolumeAmplified OR VolAmplified OR (NewLow_N>=1))
- margin_final_signal(TWSE): `NONE`; confidence: `DOWNGRADED`; unit: `億`
- margin_balance(TWSE latest): `3725.9` 億
- margin_chg(TWSE latest): `-28.8` 億
- margin_flow_audit: signal=`NONE`; sum_last5=`-95.4`; pos_days_last5=`2`
- margin_level_gate_audit: gate=`NA`; points=`30/60`; p=`NA`; p_min=`95.0`
- tw_panic_hit: `DownDay=False + Stress={}; Miss={VolumeAmplified,VolAmplified,NewLow_N>=1,ConsecutiveBreak>=2&paired}`

### TW Triggers (0/1/NA)
- TRIG_TW_PANIC: `0`
- TRIG_TW_LEVERAGE_HEAT: `0`
- TRIG_TW_REVERSAL: `0`

## Recent History (last 10 buckets)
| tpe_day | as_of_ts | bottom_state | TRIG_PANIC | TRIG_VETO | TRIG_REV | tw_state | tw_panic | tw_heat | tw_rev | margin_final | margin_conf |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|
| 2026-02-01 | 2026-02-01T23:56:52.675611+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-02 | 2026-02-02T23:55:16.505649+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-04 | 2026-02-04T13:10:37.209054+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-05 | 2026-02-05T00:04:26.107023+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-06 | 2026-02-06T00:01:05.273634+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | NA | 0 | NA | OK |
| 2026-02-07 | 2026-02-07T23:45:18.271208+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-08 | 2026-02-08T23:45:40.300617+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-10 | 2026-02-10T00:28:43.416297+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-11 | 2026-02-11T00:34:43.635609+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |

## Data Sources
- Global (single-source): `market_cache/stats_latest.json`
- TW Local Gate (existing workflow outputs, no fetch):
  - `roll25_cache/latest_report.json`
  - `taiwan_margin_cache/latest.json`
- This dashboard does not fetch external URLs directly.
