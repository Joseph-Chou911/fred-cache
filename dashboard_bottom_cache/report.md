# Bottom Cache Dashboard (v0.1)

- renderer_version: `v0.1.10`
- as_of_ts (TPE): `2026-02-26T00:38:32.185218+08:00`
- run_ts_utc: `2026-02-25T16:38:32.185201Z`
- bottom_state (Global): **NONE**  (streak=1)
- market_cache_as_of_ts: `2026-02-25T03:25:12Z`
- market_cache_generated_at_utc: `2026-02-25T03:25:12Z`
- history_load_status: `OK`; reason: `dict.items`; loaded_items: `21`
- history_pre_items: `21`; history_post_items: `22`; pre_unique_days: `21`; post_unique_days: `22`
- history_write: status=`OK`; reason=`ok`; allow_reset=`False`; allow_shrink=`False`
- history_backup: status=`OK`; reason=`copied_pre_write`; file=`dashboard_bottom_cache/history.json.bak.20260225T163832Z.json`; bytes=`19575`; keep_n=`30`; prune_deleted=`1`

## Rationale (Decision Chain) - Global
- TRIG_PANIC = `0`  (VIX >= 20.0 OR SP500.ret1% <= -1.5)
- TRIG_SYSTEMIC_VETO = `0`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)
- TRIG_REVERSAL = `0`  (panic & NOT systemic & VIX cooling & SP500 stable)

## Distance to Triggers - Global
- VIX panic gap: `0.4500`
- SP500 ret1% gap: `2.2652`
- HYG veto gap(z): `0.2054`
- OFR veto gap(z): `2.1799`

## Context (Non-trigger) - Global
- SP500.p252: `87.3015873015873`; equity_extreme(p252>=95): `0`

## TW Local Gate (roll25 + margin)
- tw_state: **NONE**  (streak=22)
- UsedDate: `2026-02-24`; run_day_tag: `WEEKDAY`; used_date_status: `DATA_NOT_UPDATED`
- Lookback: `20/20`
- roll25_raw: DownDay=`False`; VolumeAmplified=`False`; VolAmplified=`False`; NewLow_N=`0`; ConsecutiveBreak=`0`
- roll25_paired_basis: `False` (basis = VolumeAmplified OR VolAmplified OR (NewLow_N>=1))
- margin_final_signal(TWSE): `NONE`; confidence: `DOWNGRADED`; unit: `億`
- margin_balance(TWSE latest): `3831.3` 億
- margin_chg(TWSE latest): `56.3` 億
- margin_flow_audit: signal=`NONE`; sum_last5=`82.1`; pos_days_last5=`3`
- margin_level_gate_audit: gate=`NA`; points=`30/60`; p=`NA`; p_min=`95.0`
- tw_panic_hit: `DownDay=False + Stress={}; Miss={VolumeAmplified,VolAmplified,NewLow_N>=1,ConsecutiveBreak>=2&paired}`

### TW Triggers (0/1/NA)
- TRIG_TW_PANIC: `0`
- TRIG_TW_LEVERAGE_HEAT: `0`
- TRIG_TW_REVERSAL: `0`

## Recent History (last 10 buckets)
| tpe_day | as_of_ts | bottom_state | TRIG_PANIC | TRIG_VETO | TRIG_REV | tw_state | tw_panic | tw_heat | tw_rev | margin_final | margin_conf |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|
| 2026-02-15 | 2026-02-15T23:44:36.517108+08:00 | BOTTOM_CANDIDATE | 1 | 0 | 1 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-17 | 2026-02-17T00:00:15.943555+08:00 | BOTTOM_CANDIDATE | 1 | 0 | 1 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-18 | 2026-02-18T00:12:59.926117+08:00 | BOTTOM_CANDIDATE | 1 | 0 | 1 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-19 | 2026-02-19T00:13:10.706380+08:00 | BOTTOM_CANDIDATE | 1 | 0 | 1 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-20 | 2026-02-20T23:56:48.266785+08:00 | BOTTOM_WATCH | 1 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-21 | 2026-02-21T23:44:28.089780+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-22 | 2026-02-22T23:45:11.438687+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-24 | 2026-02-24T00:08:17.893960+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-25 | 2026-02-25T00:32:15.907695+08:00 | BOTTOM_WATCH | 1 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |
| 2026-02-26 | 2026-02-26T00:38:32.185218+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 0 | 0 | NONE | DOWNGRADED |

## Data Sources
- Global (single-source): `market_cache/stats_latest.json`
- TW Local Gate (existing workflow outputs, no fetch):
  - `roll25_cache/latest_report.json`
  - `taiwan_margin_cache/latest.json`
- This dashboard does not fetch external URLs directly.
