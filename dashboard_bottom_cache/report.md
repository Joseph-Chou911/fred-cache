# Bottom Cache Dashboard (v0.1)

- renderer_version: `v0.1.7`
- as_of_ts (TPE): `2026-02-01T18:08:06.357550+08:00`
- run_ts_utc: `2026-02-01T10:08:06.357539Z`
- bottom_state (Global): **NONE**  (streak=1)
- market_cache_as_of_ts: `2026-02-01T05:39:45Z`
- market_cache_generated_at_utc: `2026-02-01T05:39:45Z`
- history_load_status: `OK`; reason: `dict.items`; loaded_items: `1`
- history_pre_items: `1`; history_post_items: `1`
- history_backup: status=`OK`; reason=`copied_pre_write`; file=`dashboard_bottom_cache/history.json.bak.20260201T100806Z.json`; bytes=`1040`

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
- tw_state: **TW_BOTTOM_WATCH**  (streak=1)
- UsedDate: `2026-01-30`; run_day_tag: `WEEKEND`; used_date_status: `OK_LATEST`
- Lookback: `20/20`
- margin_final_signal(TWSE): `NONE`; confidence: `DOWNGRADED`; unit: `億`
- margin_balance(TWSE latest): `3838.9` 億
- margin_chg(TWSE latest): `21.2` 億
- margin_flow_audit: signal=`NONE`; sum_last5=`78.2`; pos_days_last5=`4`
- margin_level_gate_audit: gate=`NA`; points=`30/60`; p=`NA`; p_min=`95.0`
- tw_panic_hit: `DownDay=True + Stress={ConsecutiveBreak>=2}; Miss={VolumeAmplified,VolAmplified,NewLow_N>=1}`

### TW Triggers (0/1/NA)
- TRIG_TW_PANIC: `1`
- TRIG_TW_LEVERAGE_HEAT: `0`
- TRIG_TW_REVERSAL: `0`

## Recent History (last 10 buckets)
| tpe_day | as_of_ts | bottom_state | TRIG_PANIC | TRIG_VETO | TRIG_REV | tw_state | tw_panic | tw_heat | tw_rev | margin_final | margin_conf |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---|
| 2026-02-01 | 2026-02-01T18:08:06.357550+08:00 | NONE | 0 | 0 | 0 | TW_BOTTOM_WATCH | 1 | 0 | 0 | NONE | DOWNGRADED |

## Data Sources
- Global (single-source): `market_cache/stats_latest.json`
- TW Local Gate (existing workflow outputs, no fetch):
  - `roll25_cache/latest_report.json`
  - `taiwan_margin_cache/latest.json`
- This dashboard does not fetch external URLs directly.
