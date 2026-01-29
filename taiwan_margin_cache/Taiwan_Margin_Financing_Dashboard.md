# Taiwan Margin Financing Dashboard

## 1) 結論
- 狀態：擴張｜信號：WATCH｜資料品質：OK
  - rationale: 20D expansion + (1D%>=0.8 OR Spread20>=3 OR Accel>=0.25)
- 上游資料狀態（latest.json）：⚠️（NOTE）（top-level confidence/fetch_status/dq_reason 未提供；不做 PASS/FAIL）
- 一致性判定（Margin × Roll25）：NA（原因：ROLL25_STALE）
  - rationale: roll25 stale (UsedDateStatus=DATA_NOT_UPDATED) => strict same-day match not satisfied

## 1.1) 判定標準（本 dashboard 內建規則）
### 1) WATCH（升溫）
- 條件：20D% ≥ 8 且 (1D% ≥ 0.8 或 Spread20 ≥ 3 或 Accel ≥ 0.25)
- 行動：把你其他風險模組（VIX / 信用 / 成交量）一起對照，確認是不是同向升溫。

### 2) ALERT（疑似去槓桿）
- 條件：20D% ≥ 8 且 1D% < 0 且 5D% < 0
- 行動：優先看『是否出現連續負值』，因為可能開始踩踏。

### 3) 解除 WATCH（降溫）
- 條件：20D% 仍高，但 Accel ≤ 0 且 1D% 回到 < 0.3（需連 2–3 次確認）
- 行動：代表短線槓桿加速結束，回到『擴張但不加速』。

## 2) 資料
- 上市(TWSE)：融資餘額 3849.20 億元｜資料日期 2026-01-28｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg）
  - rows=30｜head_dates=['2026-01-28', '2026-01-27', '2026-01-26']｜tail_dates=['2025-12-18', '2025-12-17', '2025-12-16']
- 上櫃(TPEX)：融資餘額 1358.70 億元｜資料日期 2026-01-28｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg&no=TWOI）
  - rows=30｜head_dates=['2026-01-28', '2026-01-27', '2026-01-26']｜tail_dates=['2025-12-18', '2025-12-17', '2025-12-16']
- 合計：融資餘額 5207.90 億元｜資料日期 2026-01-28｜來源：TWSE=HiStock / TPEX=HiStock

## 2.0) 大盤融資維持率（proxy；僅供參考，不作為信號輸入）
- maint_path: taiwan_margin_cache/maint_ratio_latest.json
- data_date: 2026-01-28｜maint_ratio_pct: 188.131701
- totals: financing_amount_twd=384920473000, collateral_value_twd=724157432230
- coverage: included_count=1245, missing_price_count=1
- quality: fetch_status=OK, confidence=OK, dq_reason=

## 2.0.1) 大盤融資維持率（history；display-only）
- maint_hist_path: taiwan_margin_cache/maint_ratio_history.json
- history_rows: 2
- head5: [('2026-01-28', 188.131701), ('2026-01-27', 185.449854)]

## 2.1) 台股成交量/波動（roll25_cache；confirm-only）
- roll25_path: roll25_cache/latest_report.json
- UsedDate: 2026-01-28｜UsedDateStatus: DATA_NOT_UPDATED｜risk_level: NA｜tag: WEEKDAY
- summary: 今日資料未更新；UsedDate=2026-01-28：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet
- numbers: Close=32803.82, PctChange=1.5035%, TradeValue=853922428449, VolumeMultiplier=1.11749, AmplitudePct=1.305963%, VolMultiplier=1.11749
- signals: DownDay=False, VolumeAmplified=False, VolAmplified=False, NewLow_N=0, ConsecutiveBreak=0, OhlcMissing=False
- action: 維持風險控管紀律；如資料延遲或 OHLC 缺失，避免做過度解讀，待資料補齊再對照完整條件。
- caveats: Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-01-28 | UsedDminus1=2026-01-27
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
- generated_at: 2026-01-29T08:13:21.574134+08:00 (Asia/Taipei)

## 2.2) 一致性判定（Margin × Roll25 共振）
- 規則（deterministic，不猜）：
  1. 若 Margin∈{WATCH,ALERT} 且 roll25 heated（risk_level∈{中,高} 或 VolumeAmplified/VolAmplified/NewLow_N/ConsecutiveBreak 任一為 True）→ RESONANCE
  2. 若 Margin∈{WATCH,ALERT} 且 roll25 not heated → DIVERGENCE（槓桿端升溫，但市場面未放大）
  3. 若 Margin∉{WATCH,ALERT} 且 roll25 heated → MARKET_SHOCK_ONLY（市場面事件/波動主導）
  4. 其餘 → QUIET
- 判定：NA（原因：ROLL25_STALE）（roll25 stale (UsedDateStatus=DATA_NOT_UPDATED) => strict same-day match not satisfied）

## 3) 計算（以 balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）
### 上市(TWSE)
- 1D：Δ=21.90 億元；Δ%=0.5722 %｜latest=3849.20｜base=3827.30（基期日=2026-01-27）
- 5D：Δ=171.70 億元；Δ%=4.6689 %｜latest=3849.20｜base=3677.50（基期日=2026-01-21）
- 20D：Δ=435.50 億元；Δ%=12.7574 %｜latest=3849.20｜base=3413.70（基期日=2025-12-30）

### 上櫃(TPEX)
- 1D：Δ=24.20 億元；Δ%=1.8134 %｜latest=1358.70｜base=1334.50（基期日=2026-01-27）
- 5D：Δ=66.90 億元；Δ%=5.1788 %｜latest=1358.70｜base=1291.80（基期日=2026-01-21）
- 20D：Δ=192.60 億元；Δ%=16.5166 %｜latest=1358.70｜base=1166.10（基期日=2025-12-30）

### 合計(上市+上櫃)
- 1D：Δ=46.10 億元；Δ%=0.8931 %｜latest=5207.90｜base=5161.80（基期日=2026-01-27）
- 5D：Δ=238.60 億元；Δ%=4.8015 %｜latest=5207.90｜base=4969.30（基期日=2026-01-21）
- 20D：Δ=628.10 億元；Δ%=13.7146 %｜latest=5207.90｜base=4579.80（基期日=2025-12-30）

## 4) 提前示警輔助指標（不引入外部資料）
- Accel = 1D% - (5D%/5)：-0.0672
- Spread20 = TPEX_20D% - TWSE_20D%：3.7592

## 5) 稽核備註
- 合計嚴格規則：僅在『最新資料日期一致』且『該 horizon 基期日一致』時才計算合計；否則該 horizon 合計輸出 NA。
- 即使站點『融資增加(億)』欄缺失，本 dashboard 仍以 balance 序列計算 Δ/Δ%，避免依賴單一欄位。
- rows/head_dates/tail_dates 用於快速偵測抓錯頁、資料斷裂或頁面改版。
- roll25 區塊只讀取 repo 內既有 JSON（confirm-only），不在此 workflow 內重抓資料。
- roll25 若顯示 UsedDateStatus=DATA_NOT_UPDATED：代表資料延遲；Check-6 以 NOTE 呈現（非抓錯檔）。
- maint_ratio 為 proxy（display-only）：不作為 margin_signal 的輸入，僅供趨勢觀察。

## 6) 反方審核檢查（任一 Margin 失敗 → margin_quality=PARTIAL；roll25/maint 僅供對照）
- Check-0 latest.json top-level quality：⚠️（NOTE）（field may be absent; does not affect margin_quality）
- Check-1 TWSE meta_date==series[0].date：✅（PASS）
- Check-1 TPEX meta_date==series[0].date：✅（PASS）
- Check-2 TWSE head5 dates 嚴格遞減且無重複：✅（PASS）
- Check-2 TPEX head5 dates 嚴格遞減且無重複：✅（PASS）
- Check-3 TWSE/TPEX head5 完全相同（日期+餘額）視為抓錯頁：✅（PASS）
- Check-4 TWSE history rows>=21：✅（PASS）（rows=34）
- Check-4 TPEX history rows>=21：✅（PASS）（rows=34）
- Check-5 TWSE 20D base_date 存在於 series：✅（PASS）
- Check-5 TPEX 20D base_date 存在於 series：✅（PASS）
- Check-6 roll25 UsedDate 與 TWSE 最新日期一致（confirm-only）：⚠️（NOTE）（roll25 stale (UsedDateStatus=DATA_NOT_UPDATED) | UsedDate(2026-01-28) vs TWSE(2026-01-28)）
- Check-7 roll25 Lookback window（info）：⚠️（NOTE）（skipped: roll25 stale (DATA_NOT_UPDATED)）
- Check-8 maint_ratio latest readable（info）：✅（PASS）（OK）
- Check-9 maint_ratio history readable（info）：✅（PASS）（OK）
- Check-10 maint latest vs history[0] date（info）：✅（PASS）（OK）
- Check-11 maint history head5 dates 嚴格遞減且無重複（info）：✅（PASS）（OK）

_generated_at_utc: 2026-01-29T00:14:21Z_
