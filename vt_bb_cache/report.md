# VT BB Monitor Report (VT + optional USD/TWD)

- report_generated_at_utc: `2026-02-20T05:11:52Z`
- data_date: `2026-02-19`
- price_mode: `adj_close`
- params: `BB(60,2.0) on log(price)`, `forward_mdd(20D)`

## 15秒摘要
- **VT** (2026-02-19 price_usd=146.6800) → **MID_BAND** (z=1.2032, pos=0.8008); dist_to_lower=6.668%; dist_to_upper=1.732%; 20D forward_mdd: p50=-1.637%, p10=-7.279%, min=-31.571% (n=2896, conf=HIGH, conf_decision=OK, min_n_required=200)

## Forward MDD slices（摘要）
（閱讀用；不替換 bucket-conditioned 主統計。conf_decision 低於 OK 時，樣本數不足以作決策依據。）
- pos>=0.80: p50=-1.508%, p10=-5.431%, min=-31.285%, n=1704, conf=HIGH, conf_decision=OK
- dist_to_upper<=2.0%: p50=-1.443%, p10=-5.486%, min=-31.285%, n=1743, conf=HIGH, conf_decision=OK
- bucket=MID_BAND ∩ pos>=0.80: p50=-1.535%, p10=-5.186%, min=-31.285%, n=638, conf=HIGH, conf_decision=OK
- bucket=MID_BAND ∩ dist_to_upper<=2.0%: p50=-1.395%, p10=-5.322%, min=-31.285%, n=718, conf=HIGH, conf_decision=OK

## Δ1D（一日變動；以前一個「可計算 BB 的交易日」為基準）
- prev_bb_date: `2026-02-18`
- Δprice_1d: -0.224%
- Δz_1d: -0.0933
- Δpos_1d: -0.0233

## pos vs dist_to_upper 一致性檢查（提示用；不改數值）
- status: `OK`
- reason: `within_abs_or_rel_tolerance`
- expected_dist_to_upper(logband): `1.732%`
- abs_err: `0.00000000`; abs_tol: `0.00010000`
- rel_err: `0.000000`; rel_tolerance: `0.020000`

## 近 5 日（可計算 BB 的交易日；小表）

| date | price_usd | z | pos | bucket | dist_to_upper |
|---|---:|---:|---:|---|---:|
| 2026-02-12 | 145.9600 | 1.0797 | 0.7699 | MID_BAND | 2.266% |
| 2026-02-13 | 146.3400 | 1.1530 | 0.7882 | MID_BAND | 2.059% |
| 2026-02-17 | 146.2900 | 1.1138 | 0.7784 | MID_BAND | 2.102% |
| 2026-02-18 | 147.0100 | 1.2964 | 0.8241 | MID_BAND | 1.626% |
| 2026-02-19 | 146.6800 | 1.2032 | 0.8008 | MID_BAND | 1.732% |

## FX (USD/TWD)（嚴格同日對齊 + 落後參考值）
- fx_history_parse_status: `OK`
- fx_strict_used_policy: `NA`
- fx_rate_strict (for 2026-02-19): `NA`
- derived price_twd (strict): `NA`

### Reference（僅供參考；使用落後 FX 且標註落後天數）
- fx_ref_source: `HISTORY`
- fx_ref_date: `2026-02-13`
- fx_ref_rate: `31.5000`
- fx_ref_lag_days: `6`
- fx_ref_status: `OK` (stale_threshold_days=30)
- derived price_twd_ref: `4620.42`
- 說明：Reference 不會回填 strict 欄位；它只是一個「在 FX 滯後下的閱讀參考價」。

## Notes
- conf 是「樣本數分級的統計信心」；conf_decision 是「是否足夠用於決策」的門檻判定。
- conf_decision: OK 表示 n>=min_n_required；LOW_FOR_DECISION 表示樣本不足但可閱讀；NA 表示完全無樣本。
- FX strict 只接受同日對齊；來源優先 fx_history，其次 fx_latest 同日 fallback。
- FX reference 只在 strict 缺值時提供，且永不回填 strict 欄位。
