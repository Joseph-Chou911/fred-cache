# Bottom Cache Dashboard (v0)

- as_of_ts (TPE): `2026-01-30T01:25:46.779800+08:00`
- run_ts_utc: `2026-01-29T17:25:46.779786Z`
- bottom_state (Global): **NONE**  (streak=5)
- market_cache_as_of_ts: `2026-01-29T04:58:52Z`
- market_cache_generated_at_utc: `2026-01-29T04:58:52Z`

## Rationale (Decision Chain) - Global
- TRIG_PANIC = `0`  (VIX >= 20.0 OR SP500.ret1% <= -1.5)
- TRIG_SYSTEMIC_VETO = `0`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)
- TRIG_REVERSAL = `0`  (panic & NOT systemic & VIX cooling & SP500 stable)
- 因 TRIG_PANIC=0 → 不進入抄底流程（v0 設計）

## Distance to Triggers (How far from activation) - Global
- VIX panic gap = 20.0 - 16.35 = **3.6500**  (<=0 means triggered)
- SP500 ret1% gap = -0.008167827357931656 - (-1.5) = **1.4918**  (<=0 means triggered)
- HYG veto gap (z) = 1.621122452877824 - (-2.0) = **3.6211**  (<=0 means systemic veto)
- OFR veto gap (z) = (2.0) - -0.23754598259926973 = **2.2375**  (<=0 means systemic veto)

### Nearest Conditions (Top-2) - Global
- SP500 ret1% gap (<=0 triggered): `1.4918`
- OFR veto gap z (<=0 veto): `2.2375`

## Context (Non-trigger) - Global
- SP500.p252 = `99.6032`; equity_extreme(p252>=95) = `1`
- 註：處於高檔極端時，即使未來出現抄底流程訊號，也應要求更嚴格的反轉確認（僅旁註，不改 triggers）

## Triggers (0/1/NA) - Global
- TRIG_PANIC: `0`
- TRIG_SYSTEMIC_VETO: `0`
- TRIG_REVERSAL: `0`

## TW Local Gate (roll25 + margin)
- tw_state: **NONE**  (streak=5)
- UsedDate: `2026-01-28`; run_day_tag: `WEEKDAY`; risk_level: `NA`
- Lookback: `20/None`
- margin_signal(TWSE): `WATCH`; unit: `億`
- margin_balance(TWSE latest): `3817.8` 億
- margin_chg(TWSE latest): `-31.4` 億

### TW Triggers (0/1/NA)
- TRIG_TW_PANIC: `0`  (DownDay & (VolumeAmplified/VolAmplified/NewLow/ConsecutiveBreak))
- TRIG_TW_LEVERAGE_HEAT: `1`  (margin_signal∈{WATCH,ALERT})
- TRIG_TW_REVERSAL: `0`  (PANIC & NOT heat & pct_change>=0 & DownDay=false)

### TW Distances / Gating
- pct_change_to_nonnegative_gap: `1.504`
- lookback_missing_points: `NA`

### TW Snapshot (key fields)
- pct_change: `1.5035`; amplitude_pct: `1.305963`; turnover_twd: `853922428449.0`; close: `32803.82`
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
| 2026-01-30 | 2026-01-30T01:25:46.779800+08:00 | NONE | 0 | 0 | 0 | NONE | 0 | 1 | 0 | equity_extreme |

## Series Snapshot (Global)
| series_id | risk_dir | series_signal | data_date | value | w60.z | w252.p | w60.ret1_pct(%) | w60.z_delta | w60.p_delta |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| VIX | HIGH | NONE | 2026-01-28 | 16.35 | -0.27491588651563376 | 33.730158730158735 | 0.0 | 0.0052192250824261155 | 1.6666666666666643 |
| SP500 | LOW | INFO | 2026-01-28 | 6978.03 | 1.418011164238718 | 99.60317460317461 | -0.008167827357931656 | -0.05743463387786307 | -1.6666666666666714 |
| HYG_IEF_RATIO | LOW | NONE | 2026-01-28 | 0.8450469238790407 | 1.621122452877824 | 76.5873015873016 | -0.07687106823909134 | -0.19013628089061552 | -5.0 |
| OFR_FSI | HIGH | NONE | 2026-01-26 | -2.478 | -0.23754598259926973 | 11.904761904761903 | 1.0778443113772331 | 0.07893853020501168 | 3.3333333333333286 |

## Data Sources
- Global (single-source): `market_cache/stats_latest.json`
- TW Local Gate (existing workflow outputs, no fetch):
  - `roll25_cache/latest_report.json`
  - `taiwan_margin_cache/latest.json`  (unit: 億)
- This dashboard does not fetch external URLs directly.
