# 投資日記 Data Brief（roll25 + taiwan margin + tw0050_bb）

- day_key_local: 2026-02-27 (Asia/Taipei)
- generated_at_local: 2026-02-27T21:51:48.923847+08:00
- generated_at_utc: 2026-02-27T13:51:48Z
- build_fingerprint: build_video_pack@v1.2.data_only_flags_more_extracts
- warnings: NONE

## 0) Quick facts (for narration later)
- roll25 trade_value heat: 60d z=3.009 p=99.167 | 252d z=4.353 p=99.802
- margin latest: TWSE bal_yi=3898.6 chg_yi=67.3 | TPEX bal_yi=1378.5 chg_yi=30.0
- 0050 latest: state=EXTREME_UPPER_BAND bb_z=2.271 price=81.15 regime_allowed=false pledge_action=VETO

## 1) roll25 (TWSE Turnover / Heat)
- path: roll25_cache/stats_latest.json
- as_of_date: 2026-02-26 | age_days: 1 | picked_as_of_path: used_date
- fingerprint: twse_stats_v1

### extracts
- mode: FULL
- used_date: 2026-02-26
- trade_value_win60_z: 3.009013
- trade_value_win60_p: 99.167
- trade_value_win252_z: 4.352935
- trade_value_win252_p: 99.802
- close_win252_z: 2.774885
- close_win252_p: 99.802
- pct_change_win60_z: -0.465833
- pct_change_win60_p: 30.833
- amplitude_pct_win60_z: -0.274213
- amplitude_pct_win60_p: 49.167
- vol_multiplier_20: 1.451967
- volume_amplified: False
- new_low_n: 0
- consecutive_down_days: 0

### computed_flags (thresholds are explicit)
- heat_trade_value_p_ge_95_60d: True
- heat_trade_value_p_ge_99_252d: True
- index_close_p_ge_99_252d: True
- volume_amplified: False
- vol_multiplier_20_ge_1p5: False

## 2) taiwan_margin (Margin financing)
- path: taiwan_margin_cache/latest.json
- as_of_date: 2026-02-26 | age_days: 1 | picked_as_of_path: series.TWSE.data_date
- fingerprint: taiwan_margin_financing_latest_v1

### extracts
- twse_data_date: 2026-02-26
- twse_balance_yi: 3898.6
- twse_chg_yi: 67.3
- tpex_data_date: 2026-02-26
- tpex_balance_yi: 1378.5
- tpex_chg_yi: 30.0
- total_balance_yi: 5277.1
- total_chg_yi: 97.3
- twse_chg_3d_sum: 177.0
- tpex_chg_3d_sum: 56.3
- total_chg_3d_sum: 233.3
- twse_is_30row_high: True
- tpex_is_30row_high: True
- total_is_30row_high: True

### computed_flags (thresholds are explicit)
- twse_is_30row_high: True
- tpex_is_30row_high: True
- total_is_30row_high: True
- total_chg_3d_sum_ge_0: True

## 3) tw0050_bb (0050 Bollinger / Trend / Vol / Pledge gate)
- path: tw0050_bb_cache/stats_latest.json
- as_of_date: 2026-02-26 | age_days: 1 | picked_as_of_path: meta.last_date
- fingerprint: tw0050_bb60_k2_forwardmdd20@2026-02-21.v12.adjclose_audit
- dq_flags: PRICE_SERIES_BREAK_DETECTED, FWD_MDD_CLEAN_APPLIED, FWD_MDD_OUTLIER_MIN_RAW_20D, RAW_OUTLIER_EXCLUDED_BY_CLEAN

### extracts
- last_date: 2026-02-26
- adjclose: 81.1500015258789
- bb_state: EXTREME_UPPER_BAND
- bb_z: 2.2710145565515196
- dist_to_upper_pct: -1.971951060176166
- dist_to_lower_pct: 31.076676433867217
- band_width_std_pct: 34.86611093616811
- band_width_geo_pct: 42.22768704089657
- trend_state: TREND_UP
- price_vs_200ma_pct: 42.78204169364075
- trend_slope_pct: 6.473457401789284
- rv_ann: 0.21892785245279517
- rv_ann_pctl: 82.71072796934867
- regime_allowed: False
- pledge_action_bucket: VETO
- pledge_veto_reasons: ['regime_gate_closed', 'no_chase_state:EXTREME_UPPER_BAND', 'no_chase_z>= 1.50']
- tranche_levels: [{'label': '10D_p10_uncond', 'price_level': 77.25644969234536, 'drawdown': -0.04797968897501359}, {'label': '10D_p05_uncond', 'price_level': 76.03104598653216, 'drawdown': -0.06308016565735114}, {'label': '20D_p10_uncond', 'price_level': 75.57789541822046, 'drawdown': -0.06866427606759168}, {'label': '20D_p05_uncond', 'price_level': 73.62555568073307, 'drawdown': -0.09272268273151263}]

### computed_flags (thresholds are explicit)
- bb_z_ge_2: True
- rv_pctl_ge_80: True
- regime_allowed: False
- pledge_action_bucket: VETO

## 4) Notes
- This MD is data-only. Paste it back to ChatGPT for narration/script polishing.
