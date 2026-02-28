# Taiwan Margin Financing Dashboard

## 1) 結論
- 狀態：中性｜信號：NONE｜資料品質：OK
  - rationale: no rule triggered
- threshold_policy: percentile｜calib_min_n=60
  - percentiles: expansion20=90.0, contraction20=10.0, watch1d=90.0, watchspread20=90.0, watchaccel=90.0
  - thresholds_used: expansion20=8.0000, contraction20=-8.0000, watch1d=0.8000, watchspread20=3.0000, watchaccel=0.2500
  - calibration_status:
    - expansion20: status=FALLBACK_FIXED, sample_n=28, threshold=8.0, reason=insufficient samples (n=28 < calib_min_n=60)
    - contraction20: status=FALLBACK_FIXED, sample_n=28, threshold=-8.0, reason=insufficient samples (n=28 < calib_min_n=60)
    - watch1d: status=FALLBACK_FIXED, sample_n=47, threshold=0.8, reason=insufficient samples (n=47 < calib_min_n=60)
    - watchspread20: status=FALLBACK_FIXED, sample_n=28, threshold=3.0, reason=insufficient samples (n=28 < calib_min_n=60)
    - watchaccel: status=FALLBACK_FIXED, sample_n=43, threshold=0.25, reason=insufficient samples (n=43 < calib_min_n=60)
- 上游資料狀態（latest.json）：⚠️（NOTE）（top-level confidence/fetch_status/dq_reason 未提供；不做 PASS/FAIL）
- 一致性判定（Margin × Roll25）：QUIET
  - rationale: no resonance rule triggered
  - resonance_policy: latest
  - resonance_confidence: OK
- OTC_guardrail（display-only; 不影響主信號）：NONE｜stage=NONE
  - rationale: no OTC guardrail triggered
  - thresholds: thr_expansion20=8.0000, prewatch_gap=0.2000, prewatch_threshold=7.8000

## 1.1) 判定標準（本 dashboard 內建規則）
### 0) 門檻來源
- threshold_policy=percentile（percentile 若樣本不足會自動 fallback 到 fixed，並在上方 calibration_status 註明）
- fixed_baseline: expansion20=8.0, contraction20=-8.0, watch1d=0.8, watchspread20=3.0, watchaccel=0.25
- thresholds_used: expansion20=8.0000, contraction20=-8.0000, watch1d=0.8000, watchspread20=3.0000, watchaccel=0.2500

### 1) WATCH（升溫）
- 條件：20D% ≥ thr_expansion20 且 (1D% ≥ thr_watch1d 或 Spread20 ≥ thr_watchspread20 或 Accel ≥ thr_watchaccel)

### 2) ALERT（疑似去槓桿）
- 條件：20D% ≥ thr_expansion20 且 1D% < 0 且 5D% < 0

### 3) 解除 WATCH（降溫）
- 條件：20D% 仍高，但 Accel ≤ 0 且 1D% 回到 < 0.3（需連 2–3 次確認；此段仍採固定 0.3）

### 4) OTC Guardrail（display-only；不影響主信號）
- PREWATCH：TPEX_20D% ≥ (thr_expansion20 - gap)；gap=0.2000
- OTC_ALERT：TPEX_20D% ≥ thr_expansion20 且 TPEX_1D% < 0 且 TPEX_5D% < 0
- 目的：避免僅看合計（TOTAL-only）時，OTC 端先升溫/轉弱被稀釋而晚報。

## 2) 資料
- 上市(TWSE)：融資餘額 3898.60 億元｜資料日期 2026-02-26｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg）
  - rows_latest_table=30｜rows_series=48｜head_dates=['2026-02-26', '2026-02-25', '2026-02-24']｜tail_dates=['2026-01-09', '2026-01-08', '2026-01-07']
- 上櫃(TPEX)：融資餘額 1378.50 億元｜資料日期 2026-02-26｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg&no=TWOI）
  - rows_latest_table=30｜rows_series=48｜head_dates=['2026-02-26', '2026-02-25', '2026-02-24']｜tail_dates=['2026-01-09', '2026-01-08', '2026-01-07']
- 合計：融資餘額 5277.10 億元｜資料日期 2026-02-26｜來源：TWSE=HiStock / TPEX=HiStock

## 2.0) 大盤融資維持率（proxy；僅供參考，不作為信號輸入）
- maint_path: taiwan_margin_cache/maint_ratio_latest.json
- maint_ratio_policy: PROXY_TREND_ONLY
- maint_ratio_confidence: DOWNGRADED
- data_date: 2026-02-26｜maint_ratio_pct: 190.268942
- maint_ratio_1d_delta_pctpt: 0.897912｜maint_ratio_1d_pct_change: 0.474155
- maint_ratio_trend_note: trend_from: today=190.268942(2026-02-26), prev=189.37103(2026-02-25)

## 2.1) 台股成交量/波動（roll25_cache；confirm-only）
- roll25_path: roll25_cache/latest_report.json
- UsedDate: 2026-02-26｜UsedDateStatus: OK_LATEST｜risk_level: 低(derived)｜risk_level_raw: NA｜tag: WEEKEND
- summary: 今日為週末；UsedDate=2026-02-26：Mode=FULL；freshness_ok=True
- resonance_confidence: OK

## 2.2) 一致性判定（Margin × Roll25 共振）
- 判定：QUIET（no resonance rule triggered）
- resonance_confidence: OK

## 3) 計算（以 balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）
### 上市(TWSE)
- 1D：Δ=67.30 億元；Δ%=1.7566 %｜latest=3898.60｜base=3831.30（基期日=2026-02-25）
### 上櫃(TPEX)
- 1D：Δ=30.00 億元；Δ%=2.2247 %｜latest=1378.50｜base=1348.50（基期日=2026-02-25）

## 3.1) OTC Guardrail（display-only；不影響主信號）
- stage: NONE｜label: NONE
- rationale: no OTC guardrail triggered
- inputs: TPEX_20D%=5.8756｜TPEX_1D%=2.2247｜TPEX_5D%=4.2502
- thresholds: thr_expansion20=8.0000｜prewatch_threshold=7.8000

## 6) 反方審核檢查（任一 Margin 失敗 → margin_quality=PARTIAL；roll25/maint/guardrail 僅供對照）
- Check-1 TWSE meta_date==series[0].date：✅（PASS）
- Check-1 TPEX meta_date==series[0].date：✅（PASS）
- Check-2 TWSE head5 dates 嚴格遞減且無重複：✅（PASS）
- Check-2 TPEX head5 dates 嚴格遞減且無重複：✅（PASS）
- Check-3 TWSE/TPEX head5 完全相同（日期+餘額）視為抓錯頁：✅（PASS）
- Check-4 TWSE history rows>=21：✅（PASS）（rows_series=48）
- Check-4 TPEX history rows>=21：✅（PASS）（rows_series=48）
- Check-5 TWSE 20D base_date 存在於 series：✅（PASS）
- Check-5 TPEX 20D base_date 存在於 series：✅（PASS）
- Check-6 roll25 UsedDate 與 TWSE 最新日期一致（confirm-only）：✅（PASS）（OK）
- Check-7 roll25 Lookback window（info）：✅（PASS）（LookbackNActual=20/20（OK））
- Check-10 maint latest vs history[0] date（info）：✅（PASS）（OK）
- Check-11 maint history head5 dates 嚴格遞減且無重複（info）：✅（PASS）（OK）
- Check-12 OTC Guardrail（info-only）：⚠️（NOTE）（stage=NONE, label=NONE, prewatch_hit=False, otc_alert_hit=False）

_generated_at_utc: 2026-02-28T14:48:33Z_
