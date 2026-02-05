# Taiwan Margin Financing Dashboard

## 1) 結論
- 狀態：擴張｜信號：WATCH｜資料品質：OK
  - rationale: 20D expansion + (1D%>=0.8 OR Spread20>=3 OR Accel>=0.25)
- 上游資料狀態（latest.json）：⚠️（NOTE）（top-level confidence/fetch_status/dq_reason 未提供；不做 PASS/FAIL）
- 一致性判定（Margin × Roll25）：DIVERGENCE
  - rationale: Margin(WATCH/ALERT) but roll25 not heated
  - resonance_policy: latest
  - resonance_note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）
  - resonance_confidence: DOWNGRADED

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
- 上市(TWSE)：融資餘額 3840.50 億元｜資料日期 2026-02-04｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg）
  - rows=30｜head_dates=['2026-02-04', '2026-02-03', '2026-02-02']｜tail_dates=['2025-12-26', '2025-12-24', '2025-12-23']
- 上櫃(TPEX)：融資餘額 1351.00 億元｜資料日期 2026-02-04｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg&no=TWOI）
  - rows=30｜head_dates=['2026-02-04', '2026-02-03', '2026-02-02']｜tail_dates=['2025-12-26', '2025-12-24', '2025-12-23']
- 合計：融資餘額 5191.50 億元｜資料日期 2026-02-04｜來源：TWSE=HiStock / TPEX=HiStock

## 2.0) 大盤融資維持率（proxy；僅供參考，不作為信號輸入）
- maint_path: taiwan_margin_cache/maint_ratio_latest.json
- maint_ratio_policy: PROXY_TREND_ONLY
- maint_ratio_confidence: DOWNGRADED
- data_date: 2026-02-04｜maint_ratio_pct: 183.452676
- maint_ratio_1d_delta_pctpt: 3.264784｜maint_ratio_1d_pct_change: 1.811878
- maint_ratio_trend_note: trend_from: today=183.452676(2026-02-04), prev=180.187892(2026-02-03)
- totals: financing_amount_twd=384045976000, collateral_value_twd=704542620700
- coverage: included_count=1246, missing_price_count=4
- quality: fetch_status=OK, confidence=OK, dq_reason=

## 2.0.1) 大盤融資維持率（history；display-only）
- maint_hist_path: taiwan_margin_cache/maint_ratio_history.json
- history_rows: 7
- head5: [('2026-02-04', 183.452676), ('2026-02-03', 180.187892), ('2026-02-02', 178.267525), ('2026-01-30', 183.996663), ('2026-01-29', 185.890277)]

## 2.1) 台股成交量/波動（roll25_cache；confirm-only）
- roll25_path: roll25_cache/latest_report.json
- UsedDate: 2026-02-04｜UsedDateStatus: DATA_NOT_UPDATED｜risk_level: 低(derived)（stale）｜risk_level_raw: NA｜tag: WEEKDAY
- summary: 今日資料未更新；UsedDate=2026-02-04：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet
- numbers: Close=32289.81, PctChange=0.293365%, TradeValue=704644032693, VolumeMultiplier=0.890968, AmplitudePct=1.359575%, VolMultiplier=0.890968
- signals: DownDay=False, VolumeAmplified=False, VolAmplified=False, NewLow_N=0, ConsecutiveBreak=0, OhlcMissing=False
- action: 維持風險控管紀律；如資料延遲或 OHLC 缺失，避免做過度解讀，待資料補齊再對照完整條件。
- caveats: Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-02-04 | UsedDminus1=2026-02-03
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
- generated_at: 2026-02-05T08:45:10.899959+08:00 (Asia/Taipei)
- resonance_confidence: DOWNGRADED

## 2.2) 一致性判定（Margin × Roll25 共振）
- 規則（deterministic，不猜）：
  1. 若 Margin∈{WATCH,ALERT} 且 roll25 heated（risk_level∈{中,高} 或 VolumeAmplified/VolAmplified/NewLow_N/ConsecutiveBreak 任一為 True）→ RESONANCE
  2. 若 Margin∈{WATCH,ALERT} 且 roll25 not heated → DIVERGENCE（槓桿端升溫，但市場面未放大）
  3. 若 Margin∉{WATCH,ALERT} 且 roll25 heated → MARKET_SHOCK_ONLY（市場面事件/波動主導）
  4. 其餘 → QUIET
- 判定：DIVERGENCE（Margin(WATCH/ALERT) but roll25 not heated）
- resonance_confidence: DOWNGRADED
- resonance_note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## 3) 計算（以 balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）
### 上市(TWSE)
- 1D：Δ=19.20 億元；Δ%=0.5024 %｜latest=3840.50｜base=3821.30（基期日=2026-02-03）
- 5D：Δ=-8.70 億元；Δ%=-0.2260 %｜latest=3840.50｜base=3849.20（基期日=2026-01-28）
- 20D：Δ=269.90 億元；Δ%=7.5590 %｜latest=3840.50｜base=3570.60（基期日=2026-01-07）

### 上櫃(TPEX)
- 1D：Δ=13.70 億元；Δ%=1.0245 %｜latest=1351.00｜base=1337.30（基期日=2026-02-03）
- 5D：Δ=-7.70 億元；Δ%=-0.5667 %｜latest=1351.00｜base=1358.70（基期日=2026-01-28）
- 20D：Δ=135.60 億元；Δ%=11.1568 %｜latest=1351.00｜base=1215.40（基期日=2026-01-07）

### 合計(上市+上櫃)
- 1D：Δ=32.90 億元；Δ%=0.6378 %｜latest=5191.50｜base=5158.60（基期日=2026-02-03）
- 5D：Δ=-16.40 億元；Δ%=-0.3149 %｜latest=5191.50｜base=5207.90（基期日=2026-01-28）
- 20D：Δ=405.50 億元；Δ%=8.4726 %｜latest=5191.50｜base=4786.00（基期日=2026-01-07）

## 4) 提前示警輔助指標（不引入外部資料）
- Accel = 1D% - (5D%/5)：0.7008
- Spread20 = TPEX_20D% - TWSE_20D%：3.5979

## 5) 稽核備註
- 合計嚴格規則：僅在『最新資料日期一致』且『該 horizon 基期日一致』時才計算合計；否則該 horizon 合計輸出 NA。
- 即使站點『融資增加(億)』欄缺失，本 dashboard 仍以 balance 序列計算 Δ/Δ%，避免依賴單一欄位。
- rows/head_dates/tail_dates 用於快速偵測抓錯頁、資料斷裂或頁面改版。
- roll25 區塊只讀取 repo 內既有 JSON（confirm-only），不在此 workflow 內重抓資料。
- roll25 若顯示 UsedDateStatus=DATA_NOT_UPDATED：代表資料延遲；Check-6 以 NOTE 呈現（非抓錯檔）。
- resonance_policy=latest：strict 需同日且非 stale；latest 允許 stale/date mismatch 但會 resonance_confidence=DOWNGRADED。
- maint_ratio 為 proxy（display-only）：僅看趨勢與變化（Δ），不得用 proxy 絕對水位做門檻判斷。

## 6) 反方審核檢查（任一 Margin 失敗 → margin_quality=PARTIAL；roll25/maint 僅供對照）
- Check-0 latest.json top-level quality：⚠️（NOTE）（field may be absent; does not affect margin_quality）
- Check-1 TWSE meta_date==series[0].date：✅（PASS）
- Check-1 TPEX meta_date==series[0].date：✅（PASS）
- Check-2 TWSE head5 dates 嚴格遞減且無重複：✅（PASS）
- Check-2 TPEX head5 dates 嚴格遞減且無重複：✅（PASS）
- Check-3 TWSE/TPEX head5 完全相同（日期+餘額）視為抓錯頁：✅（PASS）
- Check-4 TWSE history rows>=21：✅（PASS）（rows=39）
- Check-4 TPEX history rows>=21：✅（PASS）（rows=39）
- Check-5 TWSE 20D base_date 存在於 series：✅（PASS）
- Check-5 TPEX 20D base_date 存在於 series：✅（PASS）
- Check-6 roll25 UsedDate 與 TWSE 最新日期一致（confirm-only）：⚠️（NOTE）（roll25 stale (UsedDateStatus=DATA_NOT_UPDATED) | UsedDate(2026-02-04) == TWSE(2026-02-04)）
- Check-7 roll25 Lookback window（info）：⚠️（NOTE）（skipped: roll25 stale (DATA_NOT_UPDATED)）
- Check-8 maint_ratio latest readable（info）：✅（PASS）（OK）
- Check-9 maint_ratio history readable（info）：✅（PASS）（OK）
- Check-10 maint latest vs history[0] date（info）：✅（PASS）（OK）
- Check-11 maint history head5 dates 嚴格遞減且無重複（info）：✅（PASS）（OK）

_generated_at_utc: 2026-02-05T01:09:42Z_
