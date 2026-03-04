# Episode Data (DATA-ONLY)

- day_key_local: 2026-03-04 (Asia/Taipei)
- generated_at_utc: 2026-03-04T01:48:17Z
- generated_at_local: 2026-03-04T09:48:17+08:00
- build_fingerprint: build_video_pack@v1.3.data_md_out_and_tz_fix
- warnings: NONE

## Inputs (as_of / age_days / fingerprint)

- roll25: as_of=2026-03-03 age_days=1 fingerprint=twse_stats_v1
- taiwan_margin: as_of=2026-03-03 age_days=1 fingerprint=taiwan_margin_financing_latest_v1
- tw0050_bb: as_of=2026-03-03 age_days=1 fingerprint=tw0050_bb60_k2_forwardmdd20@2026-02-21.v12.adjclose_audit

## roll25 extracts

| field | value | picked_path |
|---|---:|---|
| mode | FULL | mode |
| used_date | 2026-03-03 | used_date |
| trade_value_win60_value | 1113233319063 | series.trade_value.win60.value |
| trade_value_win60_z | 2.251656 | series.trade_value.win60.z |
| trade_value_win60_p | 97.5 | series.trade_value.win60.p |
| trade_value_win252_value | 1113233319063 | series.trade_value.win252.value |
| trade_value_win252_z | 3.595318 | series.trade_value.win252.z |
| trade_value_win252_p | 99.405 | series.trade_value.win252.p |
| close_win252_z | 2.398588 | series.close.win252.z |
| close_win252_p | 98.214 | series.close.win252.p |
| vol_multiplier_20 | 1.305799 | derived.vol_multiplier_20 |
| volume_amplified | False | derived.volume_amplified |
| new_low_n | 0 | derived.new_low_n |
| consecutive_down_days | 2 | derived.consecutive_down_days |

## taiwan_margin extracts

| field | value | picked_path |
|---|---:|---|
| twse_data_date | 2026-03-03 | series.TWSE.data_date |
| twse_balance_yi | 3843.6 | series.TWSE.rows.0.balance_yi |
| twse_chg_yi | -71.6 | series.TWSE.rows.0.chg_yi |
| tpex_data_date | 2026-03-03 | series.TPEX.data_date |
| tpex_balance_yi | 1378.7 | series.TPEX.rows.0.balance_yi |
| tpex_chg_yi | -10.4 | series.TPEX.rows.0.chg_yi |
| total_balance_yi | 5222.3 | FORMULA |
| total_chg_yi | -82 | FORMULA |
| twse_chg_sum_3rows | 13.3 | FORMULA |
| tpex_chg_sum_3rows | 30.2 | FORMULA |
| total_chg_sum_3rows | 43.5 | FORMULA |
| twse_is_30rows_high_balance | False | FORMULA |
| tpex_is_30rows_high_balance | False | FORMULA |

## tw0050_bb extracts

| field | value | picked_path |
|---|---:|---|
| last_date | 2026-03-03 | meta.last_date |
| adjclose | 78.43 | latest.adjclose |
| bb_ma | 68.416333 | latest.bb_ma |
| bb_upper | 80.49564 | latest.bb_upper |
| bb_lower | 56.337026 | latest.bb_lower |
| bb_z | 1.657987 | latest.bb_z |
| bb_state | NEAR_UPPER_BAND | latest.state |
| dist_to_upper_pct | 2.633737 | latest.dist_to_upper_pct |
| dist_to_lower_pct | 28.169035 | latest.dist_to_lower_pct |
| trend_state | TREND_UP | trend.state |
| price_vs_200ma_pct | 37.093775 | trend.price_vs_trend_ma_pct |
| trend_slope_pct | 6.567544 | trend.trend_slope_pct |
| rv_ann | 0.24068 | vol.rv_ann |
| rv_ann_pctl | 87.529919 | vol.rv_ann_pctl |
| regime_allowed | False | regime.allowed |
| pledge_action_bucket | VETO | pledge.decision.action_bucket |
| pledge_veto_reasons | ["regime_gate_closed", "no_chase_state:NEAR_UPPER_BAND", "no_chase_z>= 1.50"] | pledge.decision.veto_reasons |
| tranche_levels | [{"drawdown": -0.04797993423577851, "label": "10D_p10_uncond", "price_level": 74.66693404842135}, {"drawdown": -0.06305784033577254, "label": "10D_p05_uncond", "price_level": 73.48437386839741}, {"drawdown": -0.06866224002204649, "label": "20D_p10_uncond", "price_level": 73.04482079929262}, {"drawdown": -0.0926961270236468, "label": "20D_p05_uncond", "price_level": 71.15984303442255}] | pledge.unconditional_tranche_levels.levels |

## tw0050_bb dq.notes (first 6)

- Detected 1 break(s) by ratio thresholds; sample: 2014-01-02(r=0.249); hi=1.8, lo=0.555556.
- Computed forward_mdd_clean by excluding windows impacted by detected breaks (no price adjustment).
- forward_mdd_raw_20D min=-0.7628 < threshold(-0.4); see raw min_audit_trail.
- Primary forward_mdd uses CLEAN; raw outlier windows excluded by break mask.

