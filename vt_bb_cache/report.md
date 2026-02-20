# VT BB Monitor Report (VT + optional USD/TWD)

- report_generated_at_utc: `2026-02-20T02:04:51Z`
- data_date: `2026-02-19`
- price_mode: `adj_close`

## 15秒摘要
- **VT** (2026-02-19 price_usd=146.6800) → **MID_BAND** (z=1.2032, pos=0.8008); dist_to_lower=6.668%; dist_to_upper=1.732%; 20D forward_mdd: p50=-1.637%, p10=-7.279%, min=-31.571% (n=2896, conf=HIGH)

## FX (USD/TWD)（可選，嚴格同日對齊）
- fx_history_parse_status: `KEYS_NOT_FOUND`
- fx_used_policy: `NA`
- fx_rate (for 2026-02-19): `NA`
- derived price_twd: `NA`

## Notes
- forward_mdd20 理論上應永遠 <= 0；若你看到 >0，代表資料對齊或定義出錯。
- 若 FX 無同日資料，TWD 相關欄位會是 NA（不做 nearest / latest 代入）。
