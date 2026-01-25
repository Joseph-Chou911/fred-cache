# Bottom Cache Dashboard (v0)

- as_of_ts (TPE): `2026-01-25T18:07:12.953810+08:00`
- run_ts_utc: `2026-01-25T10:07:12.953796Z`
- bottom_state: **NONE**

## Rationale (Decision Chain)
- TRIG_PANIC = `0`  (VIX >= 20.0 OR SP500.ret1% <= -1.5)
- TRIG_SYSTEMIC_VETO = `0`  (systemic veto via HYG_IEF_RATIO / OFR_FSI)
- TRIG_REVERSAL = `0`  (panic & NOT systemic & VIX cooling & SP500 stable)
- 因 TRIG_PANIC=0 → 不進入抄底流程（v0 設計）

## Distance to Triggers (How far from activation)
- VIX panic gap = 20.0 - 16.09 = **3.9100**  (<=0 means triggered)
- SP500 ret1% gap = 0.03269037442049526 - (-1.5) = **1.5327**  (<=0 means triggered)
- HYG veto gap (z) = 1.9723169759073098 - (-2.0) = **3.9723**  (<=0 means systemic veto)
- OFR veto gap (z) = (2.0) - -0.16853631919646242 = **2.1685**  (<=0 means systemic veto)

## Triggers (0/1/NA)
- TRIG_PANIC: `0`
- TRIG_SYSTEMIC_VETO: `0`
- TRIG_REVERSAL: `0`

## Action Map (v0)
- NONE: 維持既定 DCA/資產配置紀律；不把它當成抄底時點訊號
- BOTTOM_WATCH: 只做準備（現金/分批計畫/撤退條件），不進場
- BOTTOM_CANDIDATE: 允許分批（例如 2–3 段），但需設定撤退條件
- PANIC_BUT_SYSTEMIC: 不抄底，先等信用/壓力解除

## Series Snapshot
| series_id | risk_dir | series_signal | data_date | value | w60.z | w252.p | w60.ret1_pct(%) | w60.z_delta | w60.p_delta |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| VIX | HIGH | NONE | 2026-01-23 | 16.09 | -0.38809606605851577 | 28.57142857142857 | 2.8772378516623993 | 0.172147211058723 | 13.333333333333336 |
| SP500 | LOW | INFO | 2026-01-23 | 6915.61 | 0.867813687185047 | 95.63492063492063 | 0.03269037442049526 | 0.012874360472983959 | 0.0 |
| HYG_IEF_RATIO | LOW | NONE | 2026-01-23 | 0.8456487754038562 | 1.9723169759073098 | 78.96825396825396 | -0.2159445726344131 | -0.477955336205953 | -5.0 |
| OFR_FSI | HIGH | NONE | 2026-01-21 | -2.445 | -0.16853631919646242 | 15.079365079365079 | -11.389521640091118 | -0.7038906118856403 | -28.333333333333336 |
