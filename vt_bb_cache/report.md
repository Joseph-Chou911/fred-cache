# VT BB Monitor Report (VT + optional USD/TWD)

- report_generated_at_utc: `2026-02-20T02:40:26Z`
- data_date: `2026-02-19`
- price_mode: `adj_close`
- params: `BB(60,2.0) on log(price)`, `forward_mdd(20D)`

## 15秒摘要
- **VT** (2026-02-19 price_usd=146.6800) → **MID_BAND** (z=1.2032, pos=0.8008); dist_to_lower=6.668%; dist_to_upper=1.732%; 20D forward_mdd: p50=-1.637%, p10=-7.279%, min=-31.571% (n=2896, conf=HIGH)

## 解讀重點（更詳盡）
- **Band 位置**：pos=0.8008（>0.80 視為「靠近上緣」的閱讀提示；此提示不改 bucket 規則）
- **距離上下軌**：dist_to_upper=1.732%；dist_to_lower=6.668%
- **波動區間寬度（閱讀用）**：band_width≈9.000%（= upper/lower - 1；用於直覺理解，不作信號）
- **forward_mdd(20D)**：p50=-1.637%、p10=-7.279%、min=-31.571%；n=2896（conf=HIGH）
- **閱讀提示**：pos≥0.80 → 價格相對靠近上緣（但 z 未必達到 NEAR_UPPER 的門檻）

## BB 詳細（可稽核欄位）

| field | value | note |
|---|---:|---|
| price_usd | 146.6800 | adj_close |
| close_usd | 146.6800 | raw close (for reference) |
| z | 1.2032 | log(price) z-score vs BB mean/stdev |
| pos_in_band | 0.8008 | (logp-lower)/(upper-lower) clipped [0,1] |
| lower_usd | 136.8987 | exp(lower_log) |
| upper_usd | 149.2199 | exp(upper_log) |
| dist_to_lower | 6.668% | (price-lower)/price |
| dist_to_upper | 1.732% | (upper-price)/price |
| bucket | MID_BAND | based on z thresholds |

## forward_mdd(20D)（分布解讀）

- 定義：對每一天 t，觀察未來 N 天（t+1..t+N）中的**最低價**相對於當日價的跌幅：min(future)/p0 - 1。
- 理論限制：此值應永遠 <= 0；若 >0，代表對齊/定義錯誤（或資料異常）。
- 你目前看到的是 **bucket=MID_BAND** 條件下的歷史樣本分布（不是預測）：
  - p50=-1.637%（中位數回撤）
  - p10=-7.279%（偏壞情境，約最差 10%）
  - min=-31.571%（歷史最極端尾部）
  - n=2896（樣本數）；conf=HIGH

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

## Data Quality / Staleness 提示（不改數值，只提示狀態）
- FX strict 缺值，已提供 Reference；lag_days=6。
- 若遇到長假/休市期間，FX strict 為 NA 屬於正常現象；Reference 會明確標註落後天數。

## Notes
- forward_mdd 理論上應永遠 <= 0；若你看到 >0，代表資料對齊或定義出錯。
- bucket 目前以 z 門檻定義；pos≥0.80/≤0.20 僅作閱讀提示，不改信號。
- FX strict 欄位不會用落後匯率填補；落後匯率只會出現在 Reference 區塊。
