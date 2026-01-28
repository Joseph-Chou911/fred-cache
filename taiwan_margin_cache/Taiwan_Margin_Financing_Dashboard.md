# Taiwan Margin Financing Dashboard

## 1) 結論
- 狀態：擴張｜信號：NONE｜資料品質：PARTIAL
  - rationale: no rule triggered
- 上游資料狀態（latest.json）：confidence=NA｜fetch_status=NA｜dq_reason=NA
- 一致性判定（Margin × Roll25）：NA
  - rationale: roll25 missing/mismatch => resonance NA (strict)

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
- 上市(TWSE)：融資餘額 3827.30 億元｜資料日期 2026-01-27｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg）
  - rows=30｜head_dates=['2026-01-27', '2026-01-26', '2026-01-23']｜tail_dates=['2025-12-17', '2025-12-16', '2025-12-15']
- 上櫃(TPEX)：融資餘額 1334.50 億元｜資料日期 2026-01-27｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg&no=TWOI）
  - rows=30｜head_dates=['2026-01-27', '2026-01-26', '2026-01-23']｜tail_dates=['2025-12-17', '2025-12-16', '2025-12-15']
- 合計：融資餘額 5161.80 億元｜資料日期 2026-01-27｜來源：TWSE=HiStock / TPEX=HiStock

## 2.0) 大盤融資維持率（proxy；僅供參考，不作為信號輸入）
- maint_path: NA
- maint_error: maint path not provided

## 2.1) 台股成交量/波動（roll25_cache；confirm-only）
- roll25_path: roll25_cache/latest_report.json
- UsedDate: 2026-01-26｜risk_level: NA｜tag: WEEKDAY
- summary: 今日資料未更新；UsedDate=2026-01-26：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet
- numbers: Close=32064.52, PctChange=0.322294%, TradeValue=747339306040, VolumeMultiplier=1.027252, AmplitudePct=0.64731%, VolMultiplier=1.027252
- signals: DownDay=False, VolumeAmplified=False, VolAmplified=False, NewLow_N=0, ConsecutiveBreak=0, OhlcMissing=False
- action: 維持風險控管紀律；如資料延遲或 OHLC 缺失，避免做過度解讀，待資料補齊再對照完整條件。
- caveats: Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-01-26 | UsedDminus1=2026-01-23
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=2
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
- generated_at: 2026-01-28T03:37:25.116192+08:00 (Asia/Taipei)

## 2.2) 一致性判定（Margin × Roll25 共振）
- 規則（deterministic，不猜）：
  1. 若 Margin∈{WATCH,ALERT} 且 roll25 heated（risk_level∈{中,高} 或 VolumeAmplified/VolAmplified/NewLow_N/ConsecutiveBreak 任一為 True）→ RESONANCE
  2. 若 Margin∈{WATCH,ALERT} 且 roll25 not heated → DIVERGENCE（槓桿端升溫，但市場面未放大）
  3. 若 Margin∉{WATCH,ALERT} 且 roll25 heated → MARKET_SHOCK_ONLY（市場面事件/波動主導）
  4. 其餘 → QUIET
- 判定：NA（roll25 missing/mismatch => resonance NA (strict)）

## 3) 計算（以 balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）
### 上市(TWSE)
- 1D：Δ=11.50 億元；Δ%=0.3014 %｜latest=3827.30｜base=3815.80（基期日=2026-01-26）
- 5D：Δ=115.00 億元；Δ%=3.0978 %｜latest=3827.30｜base=3712.30（基期日=2026-01-20）
- 20D：Δ=428.40 億元；Δ%=12.6041 %｜latest=3827.30｜base=3398.90（基期日=2025-12-29）

### 上櫃(TPEX)
- 1D：Δ=11.60 億元；Δ%=0.8769 %｜latest=1334.50｜base=1322.90（基期日=2026-01-26）
- 5D：Δ=32.50 億元；Δ%=2.4962 %｜latest=1334.50｜base=1302.00（基期日=2026-01-20）
- 20D：Δ=176.80 億元；Δ%=15.2717 %｜latest=1334.50｜base=1157.70（基期日=2025-12-29）

### 合計(上市+上櫃)
- 1D：Δ=23.10 億元；Δ%=0.4495 %｜latest=5161.80｜base=5138.70（基期日=2026-01-26）
- 5D：Δ=147.50 億元；Δ%=2.9416 %｜latest=5161.80｜base=5014.30（基期日=2026-01-20）
- 20D：Δ=605.20 億元；Δ%=13.2818 %｜latest=5161.80｜base=4556.60（基期日=2025-12-29）

## 4) 提前示警輔助指標（不引入外部資料）
- Accel = 1D% - (5D%/5)：-0.1388
- Spread20 = TPEX_20D% - TWSE_20D%：2.6676

## 5) 稽核備註
- 合計嚴格規則：僅在『最新資料日期一致』且『該 horizon 基期日一致』時才計算合計；否則該 horizon 合計輸出 NA。
- 即使站點『融資增加(億)』欄缺失，本 dashboard 仍以 balance 序列計算 Δ/Δ%，避免依賴單一欄位。
- rows/head_dates/tail_dates 用於快速偵測抓錯頁、資料斷裂或頁面改版。
- roll25 區塊只讀取 repo 內既有 JSON（confirm-only），不在此 workflow 內重抓資料。
- roll25 LookbackNActual 未滿 target 時：只做『信心降級註記』，不改 margin 資料品質。
- maint_ratio 為 proxy（display-only）：不作為 margin_signal 的輸入，僅供趨勢觀察。
- 若 latest.json 顯示 confidence/fetch_status 非 OK：本報告會將 margin_quality 降為 PARTIAL（但不改 signal）。

## 6) 反方審核檢查（任一 Margin 失敗 → margin_quality=PARTIAL；roll25/maint 僅供對照）
- Check-0 latest.json top-level quality OK：❌（FAIL）（confidence=NA, fetch_status=NA, dq_reason=NA）
- Check-1 TWSE meta_date==series[0].date：✅（OK）
- Check-1 TPEX meta_date==series[0].date：✅（OK）
- Check-2 TWSE head5 dates 嚴格遞減且無重複：✅（OK）
- Check-2 TPEX head5 dates 嚴格遞減且無重複：✅（OK）
- Check-3 TWSE/TPEX head5 完全相同（日期+餘額）視為抓錯頁：✅（OK）
- Check-4 TWSE history rows>=21：✅（OK）（rows=33）
- Check-4 TPEX history rows>=21：✅（OK）（rows=33）
- Check-5 TWSE 20D base_date 存在於 series：✅（OK）
- Check-5 TPEX 20D base_date 存在於 series：✅（OK）
- Check-6 roll25 UsedDate 與 TWSE 最新日期一致（confirm-only）：❌（FAIL）（UsedDate(2026-01-26) != TWSE meta_date(2026-01-27) or roll25 missing）
- Check-7 roll25 Lookback window（info）：⚠️（NOTE）（skipped: roll25 strict mismatch/missing）
- Check-8 maint_ratio file readable（info）：⚠️（NOTE）（skipped: --maint not provided）

_generated_at_utc: 2026-01-28T01:11:24Z_
