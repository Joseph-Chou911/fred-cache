# Episode Data (DATA-ONLY)

- day_key_local: 2026-03-11 (Asia/Taipei)
- generated_at_utc: 2026-03-10T23:57:06Z
- generated_at_local: 2026-03-11T07:57:06+08:00
- build_fingerprint: build_video_pack@v1.3.data_md_out_and_tz_fix
- warnings: NONE

## Inputs (as_of / age_days / fingerprint)

- roll25: as_of=2026-03-10 age_days=1 fingerprint=twse_stats_v1
- taiwan_margin: as_of=2026-03-10 age_days=1 fingerprint=taiwan_margin_financing_latest_v1
- tw0050_bb: as_of=2026-03-10 age_days=1 fingerprint=tw0050_bb60_k2_forwardmdd20@2026-02-21.v12.adjclose_audit

## roll25 extracts

| field | value | picked_path |
|---|---:|---|
| mode | FULL | mode |
| used_date | 2026-03-10 | used_date |
| trade_value_win60_value | 728225719000 | series.trade_value.win60.value |
| trade_value_win60_z | 0.11438 | series.trade_value.win60.z |
| trade_value_win60_p | 54.167 | series.trade_value.win60.p |
| trade_value_win252_value | 728225719000 | series.trade_value.win252.value |
| trade_value_win252_z | 1.316534 | series.trade_value.win252.z |
| trade_value_win252_p | 88.69 | series.trade_value.win252.p |
| close_win252_z | 1.872855 | series.close.win252.z |
| close_win252_p | 95.04 | series.close.win252.p |
| vol_multiplier_20 | 0.856809 | derived.vol_multiplier_20 |
| volume_amplified | False | derived.volume_amplified |
| new_low_n | 0 | derived.new_low_n |
| consecutive_down_days | 0 | derived.consecutive_down_days |

## taiwan_margin extracts

| field | value | picked_path |
|---|---:|---|
| twse_data_date | 2026-03-10 | series.TWSE.data_date |
| twse_balance_yi | 3682.4 | series.TWSE.rows.0.balance_yi |
| twse_chg_yi | -37.2 | series.TWSE.rows.0.chg_yi |
| tpex_data_date | 2026-03-10 | series.TPEX.data_date |
| tpex_balance_yi | 1322.1 | series.TPEX.rows.0.balance_yi |
| tpex_chg_yi | 6.3 | series.TPEX.rows.0.chg_yi |
| total_balance_yi | 5004.5 | FORMULA |
| total_chg_yi | -30.9 | FORMULA |
| twse_chg_sum_3rows | -109.2 | FORMULA |
| tpex_chg_sum_3rows | -61.9 | FORMULA |
| total_chg_sum_3rows | -171.1 | FORMULA |
| twse_is_30rows_high_balance | False | FORMULA |
| tpex_is_30rows_high_balance | False | FORMULA |

## tw0050_bb extracts

| field | value | picked_path |
|---|---:|---|
| last_date | 2026-03-10 | meta.last_date |
| adjclose | 75.199997 | latest.adjclose |
| bb_ma | 69.657464 | latest.bb_ma |
| bb_upper | 81.478417 | latest.bb_upper |
| bb_lower | 57.83651 | latest.bb_lower |
| bb_z | 0.937747 | latest.bb_z |
| bb_state | IN_BAND | latest.state |
| dist_to_upper_pct | 8.348964 | latest.dist_to_upper_pct |
| dist_to_lower_pct | 23.089744 | latest.dist_to_lower_pct |
| trend_state | TREND_UP | trend.state |
| price_vs_200ma_pct | 29.576913 | trend.price_vs_trend_ma_pct |
| trend_slope_pct | 6.397008 | trend.trend_slope_pct |
| rv_ann | 0.335764 | vol.rv_ann |
| rv_ann_pctl | 96.342338 | vol.rv_ann_pctl |
| regime_allowed | False | regime.allowed |
| pledge_action_bucket | VETO | pledge.decision.action_bucket |
| pledge_veto_reasons | ["regime_gate_closed"] | pledge.decision.veto_reasons |
| tranche_levels | [{"drawdown": -0.047979578112139154, "label": "10D_p10_uncond", "price_level": 71.59193282063137}, {"drawdown": -0.0630158683943165, "label": "10D_p05_uncond", "price_level": 70.46120383729875}, {"drawdown": -0.06864997898061322, "label": "20D_p10_uncond", "price_level": 70.03751873840318}, {"drawdown": -0.09264445043853842, "label": "20D_p05_uncond", "price_level": 68.23313455799253}] | pledge.unconditional_tranche_levels.levels |

## tw0050_bb dq.notes (first 6)

- Detected 1 break(s) by ratio thresholds; sample: 2014-01-02(r=0.249); hi=1.8, lo=0.555556.
- Computed forward_mdd_clean by excluding windows impacted by detected breaks (no price adjustment).
- forward_mdd_raw_20D min=-0.7628 < threshold(-0.4); see raw min_audit_trail.
- Primary forward_mdd uses CLEAN; raw outlier windows excluded by break mask.

