# Episode Data (DATA-ONLY)

- day_key_local: 2026-02-27 (Asia/Taipei)
- generated_at_utc: 2026-02-27T13:58:03Z
- generated_at_local: 2026-02-27T21:58:03+08:00
- build_fingerprint: build_video_pack@v1.3.data_md_out_and_tz_fix
- warnings: NONE

## Inputs (as_of / age_days / fingerprint)

- roll25: as_of=2026-02-26 age_days=1 fingerprint=twse_stats_v1
- taiwan_margin: as_of=2026-02-26 age_days=1 fingerprint=taiwan_margin_financing_latest_v1
- tw0050_bb: as_of=2026-02-26 age_days=1 fingerprint=tw0050_bb60_k2_forwardmdd20@2026-02-21.v12.adjclose_audit

## roll25 extracts

| field | value | picked_path |
|---|---:|---|
| mode | FULL | mode |
| used_date | 2026-02-26 | used_date |
| trade_value_win60_value | 1207836722507 | series.trade_value.win60.value |
| trade_value_win60_z | 3.009013 | series.trade_value.win60.z |
| trade_value_win60_p | 99.167 | series.trade_value.win60.p |
| trade_value_win252_value | 1207836722507 | series.trade_value.win252.value |
| trade_value_win252_z | 4.352935 | series.trade_value.win252.z |
| trade_value_win252_p | 99.802 | series.trade_value.win252.p |
| close_win252_z | 2.774885 | series.close.win252.z |
| close_win252_p | 99.802 | series.close.win252.p |
| vol_multiplier_20 | 1.451967 | derived.vol_multiplier_20 |
| volume_amplified | False | derived.volume_amplified |
| new_low_n | 0 | derived.new_low_n |
| consecutive_down_days | 0 | derived.consecutive_down_days |

## taiwan_margin extracts

| field | value | picked_path |
|---|---:|---|
| twse_data_date | 2026-02-26 | series.TWSE.data_date |
| twse_balance_yi | 3898.6 | series.TWSE.rows.0.balance_yi |
| twse_chg_yi | 67.3 | series.TWSE.rows.0.chg_yi |
| tpex_data_date | 2026-02-26 | series.TPEX.data_date |
| tpex_balance_yi | 1378.5 | series.TPEX.rows.0.balance_yi |
| tpex_chg_yi | 30 | series.TPEX.rows.0.chg_yi |
| total_balance_yi | 5277.1 | FORMULA |
| total_chg_yi | 97.3 | FORMULA |
| twse_chg_sum_3rows | 177 | FORMULA |
| tpex_chg_sum_3rows | 56.3 | FORMULA |
| total_chg_sum_3rows | 233.3 | FORMULA |
| twse_is_30rows_high_balance | True | FORMULA |
| tpex_is_30rows_high_balance | True | FORMULA |

## tw0050_bb extracts

| field | value | picked_path |
|---|---:|---|
| last_date | 2026-02-26 | meta.last_date |
| adjclose | 81.150002 | latest.adjclose |
| bb_ma | 67.740521 | latest.bb_ma |
| bb_upper | 79.549763 | latest.bb_upper |
| bb_lower | 55.931278 | latest.bb_lower |
| bb_z | 2.271015 | latest.bb_z |
| bb_state | EXTREME_UPPER_BAND | latest.state |
| dist_to_upper_pct | -1.971951 | latest.dist_to_upper_pct |
| dist_to_lower_pct | 31.076676 | latest.dist_to_lower_pct |
| trend_state | TREND_UP | trend.state |
| price_vs_200ma_pct | 42.782042 | trend.price_vs_trend_ma_pct |
| trend_slope_pct | 6.473457 | trend.trend_slope_pct |
| rv_ann | 0.218928 | vol.rv_ann |
| rv_ann_pctl | 82.710728 | vol.rv_ann_pctl |
| regime_allowed | False | regime.allowed |
| pledge_action_bucket | VETO | pledge.decision.action_bucket |
| pledge_veto_reasons | ["regime_gate_closed", "no_chase_state:EXTREME_UPPER_BAND", "no_chase_z>= 1.50"] | pledge.decision.veto_reasons |
| tranche_levels | [{"drawdown": -0.04797968897501359, "label": "10D_p10_uncond", "price_level": 77.25644969234536}, {"drawdown": -0.06308016565735114, "label": "10D_p05_uncond", "price_level": 76.03104598653216}, {"drawdown": -0.06866427606759168, "label": "20D_p10_uncond", "price_level": 75.57789541822046}, {"drawdown": -0.09272268273151263, "label": "20D_p05_uncond", "price_level": 73.62555568073307}] | pledge.unconditional_tranche_levels.levels |

## tw0050_bb dq.notes (first 6)

- Detected 1 break(s) by ratio thresholds; sample: 2014-01-02(r=0.249); hi=1.8, lo=0.555556.
- Computed forward_mdd_clean by excluding windows impacted by detected breaks (no price adjustment).
- forward_mdd_raw_20D min=-0.7628 < threshold(-0.4); see raw min_audit_trail.
- Primary forward_mdd uses CLEAN; raw outlier windows excluded by break mask.

