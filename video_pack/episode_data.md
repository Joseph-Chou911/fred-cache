# Episode Data (DATA-ONLY)

- day_key_local: 2026-03-03 (Asia/Taipei)
- generated_at_utc: 2026-03-03T12:42:16Z
- generated_at_local: 2026-03-03T20:42:16+08:00
- build_fingerprint: build_video_pack@v1.3.data_md_out_and_tz_fix
- warnings: NONE

## Inputs (as_of / age_days / fingerprint)

- roll25: as_of=2026-03-02 age_days=1 fingerprint=twse_stats_v1
- taiwan_margin: as_of=2026-03-02 age_days=1 fingerprint=taiwan_margin_financing_latest_v1
- tw0050_bb: as_of=2026-03-03 age_days=0 fingerprint=tw0050_bb60_k2_forwardmdd20@2026-02-21.v12.adjclose_audit

## roll25 extracts

| field | value | picked_path |
|---|---:|---|
| mode | FULL | mode |
| used_date | 2026-03-02 | used_date |
| trade_value_win60_value | 1014040137978 | series.trade_value.win60.value |
| trade_value_win60_z | 1.859307 | series.trade_value.win60.z |
| trade_value_win60_p | 95.833 | series.trade_value.win60.p |
| trade_value_win252_value | 1014040137978 | series.trade_value.win252.value |
| trade_value_win252_z | 3.131434 | series.trade_value.win252.z |
| trade_value_win252_p | 99.008 | series.trade_value.win252.p |
| close_win252_z | 2.640655 | series.close.win252.z |
| close_win252_p | 99.008 | series.close.win252.p |
| vol_multiplier_20 | 1.210652 | derived.vol_multiplier_20 |
| volume_amplified | False | derived.volume_amplified |
| new_low_n | 0 | derived.new_low_n |
| consecutive_down_days | 1 | derived.consecutive_down_days |

## taiwan_margin extracts

| field | value | picked_path |
|---|---:|---|
| twse_data_date | 2026-03-02 | series.TWSE.data_date |
| twse_balance_yi | 3916.2 | series.TWSE.rows.0.balance_yi |
| twse_chg_yi | 17.6 | series.TWSE.rows.0.chg_yi |
| tpex_data_date | 2026-03-02 | series.TPEX.data_date |
| tpex_balance_yi | 1389.1 | series.TPEX.rows.0.balance_yi |
| tpex_chg_yi | 10.6 | series.TPEX.rows.0.chg_yi |
| total_balance_yi | 5305.3 | FORMULA |
| total_chg_yi | 28.2 | FORMULA |
| twse_chg_sum_3rows | 141.2 | FORMULA |
| tpex_chg_sum_3rows | 52.6 | FORMULA |
| total_chg_sum_3rows | 193.8 | FORMULA |
| twse_is_30rows_high_balance | True | FORMULA |
| tpex_is_30rows_high_balance | True | FORMULA |

## tw0050_bb extracts

| field | value | picked_path |
|---|---:|---|
| last_date | 2026-03-03 | meta.last_date |
| adjclose | 78.75 | latest.adjclose |
| bb_ma | 68.421667 | latest.bb_ma |
| bb_upper | 80.518923 | latest.bb_upper |
| bb_lower | 56.32441 | latest.bb_lower |
| bb_z | 1.70755 | latest.bb_z |
| bb_state | NEAR_UPPER_BAND | latest.state |
| dist_to_upper_pct | 2.246252 | latest.dist_to_upper_pct |
| dist_to_lower_pct | 28.47694 | latest.dist_to_lower_pct |
| trend_state | TREND_UP | trend.state |
| price_vs_200ma_pct | 37.649277 | trend.price_vs_trend_ma_pct |
| trend_slope_pct | 6.570524 | trend.trend_slope_pct |
| rv_ann | 0.234926 | vol.rv_ann |
| rv_ann_pctl | 86.596458 | vol.rv_ann_pctl |
| regime_allowed | False | regime.allowed |
| pledge_action_bucket | VETO | pledge.decision.action_bucket |
| pledge_veto_reasons | ["regime_gate_closed", "no_chase_state:NEAR_UPPER_BAND", "no_chase_z>= 1.50"] | pledge.decision.veto_reasons |
| tranche_levels | [{"drawdown": -0.047979817489179455, "label": "10D_p10_uncond", "price_level": 74.97158937272712}, {"drawdown": -0.06305813304751152, "label": "10D_p05_uncond", "price_level": 73.78417202250847}, {"drawdown": -0.06866230312395323, "label": "20D_p10_uncond", "price_level": 73.34284362898867}, {"drawdown": -0.0926959461182094, "label": "20D_p05_uncond", "price_level": 71.450194243191}] | pledge.unconditional_tranche_levels.levels |

## tw0050_bb dq.notes (first 6)

- Detected 1 break(s) by ratio thresholds; sample: 2014-01-02(r=0.249); hi=1.8, lo=0.555556.
- Computed forward_mdd_clean by excluding windows impacted by detected breaks (no price adjustment).
- forward_mdd_raw_20D min=-0.7628 < threshold(-0.4); see raw min_audit_trail.
- Primary forward_mdd uses CLEAN; raw outlier windows excluded by break mask.

