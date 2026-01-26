# Taiwan Margin Financing Dashboard

## 1) 結論
- 狀態：擴張｜信號：WATCH｜資料品質：OK
  - rationale: 20D expansion + (1D%>=0.8 OR Spread20>=3 OR Accel>=0.25)
- 一致性判定（Margin × Roll25）：DIVERGENCE
  - rationale: Margin(WATCH/ALERT) but roll25 not heated
  - roll25_window_note: LookbackNActual=17/20（window 未滿 → 信心降級）

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
- 上市(TWSE)：融資餘額 3815.80 億元｜資料日期 2026-01-26｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg）
  - rows=30｜head_dates=['2026-01-26', '2026-01-23', '2026-01-22']｜tail_dates=['2025-12-16', '2025-12-15', '2025-12-12']
- 上櫃(TPEX)：融資餘額 1322.90 億元｜資料日期 2026-01-26｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg&no=TWOI）
  - rows=30｜head_dates=['2026-01-26', '2026-01-23', '2026-01-22']｜tail_dates=['2025-12-16', '2025-12-15', '2025-12-12']
- 合計：融資餘額 5138.70 億元｜資料日期 2026-01-26｜來源：TWSE=HiStock / TPEX=HiStock

## 2.1) 台股成交量/波動（roll25_cache；confirm-only）
- roll25_path: roll25_cache/latest_report.json
- UsedDate: 2026-01-26｜risk_level: 低｜tag: DATA_NOT_UPDATED
- summary: 今日資料未更新；UsedDate=2026-01-26：未觸發 A) 規則；風險等級=低
- numbers: Close=32064.52, PctChange=0.322%, TradeValue=747339306040, VolumeMultiplier=0.971, AmplitudePct=0.647%, VolMultiplier=0.46
- signals: DownDay=False, VolumeAmplified=False, VolAmplified=False, NewLow_N=False, ConsecutiveBreak=False, OhlcMissing=False
- action: 維持風險控管紀律（槓桿與保證金緩衝不惡化），持續每日觀察量能倍數、是否破位與資料完整性。
- caveats: Sources: FMTQIK=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; MI_5MINS_HIST=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Mode=FULL | UsedDate=2026-01-26 | UsedDminus1=2026-01-23 | LookbackNTarget=20 | LookbackNActual=17 | LookbackOldest=2026-01-02 | OHLC=OK
- generated_at: 2026-01-27T07:38:12.456448+08:00 (Asia/Taipei)

## 2.2) 一致性判定（Margin × Roll25 共振）
- 規則（deterministic，不猜）：
  1. 若 Margin∈{WATCH,ALERT} 且 roll25 heated（risk_level∈{中,高} 或 VolumeAmplified/VolAmplified/NewLow_N/ConsecutiveBreak 任一為 True）→ RESONANCE
  2. 若 Margin∈{WATCH,ALERT} 且 roll25 not heated → DIVERGENCE（槓桿端升溫，但市場面未放大）
  3. 若 Margin∉{WATCH,ALERT} 且 roll25 heated → MARKET_SHOCK_ONLY（市場面事件/波動主導）
  4. 其餘 → QUIET
- 判定：DIVERGENCE（Margin(WATCH/ALERT) but roll25 not heated）

## 3) 計算（以 balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）
### 上市(TWSE)
- 1D：Δ=55.00 億元；Δ%=1.4625 %｜latest=3815.80｜base=3760.80（基期日=2026-01-23）
- 5D：Δ=121.60 億元；Δ%=3.2916 %｜latest=3815.80｜base=3694.20（基期日=2026-01-19）
- 20D：Δ=412.40 億元；Δ%=12.1173 %｜latest=3815.80｜base=3403.40（基期日=2025-12-26）

### 上櫃(TPEX)
- 1D：Δ=10.40 億元；Δ%=0.7924 %｜latest=1322.90｜base=1312.50（基期日=2026-01-23）
- 5D：Δ=33.40 億元；Δ%=2.5902 %｜latest=1322.90｜base=1289.50（基期日=2026-01-19）
- 20D：Δ=169.20 億元；Δ%=14.6659 %｜latest=1322.90｜base=1153.70（基期日=2025-12-26）

### 合計(上市+上櫃)
- 1D：Δ=65.40 億元；Δ%=1.2891 %｜latest=5138.70｜base=5073.30（基期日=2026-01-23）
- 5D：Δ=155.00 億元；Δ%=3.1101 %｜latest=5138.70｜base=4983.70（基期日=2026-01-19）
- 20D：Δ=581.60 億元；Δ%=12.7625 %｜latest=5138.70｜base=4557.10（基期日=2025-12-26）

## 4) 提前示警輔助指標（不引入外部資料）
- Accel = 1D% - (5D%/5)：0.6671
- Spread20 = TPEX_20D% - TWSE_20D%：2.5486

## 5) 稽核備註
- 合計嚴格規則：僅在『最新資料日期一致』且『該 horizon 基期日一致』時才計算合計；否則該 horizon 合計輸出 NA。
- 即使站點『融資增加(億)』欄缺失，本 dashboard 仍以 balance 序列計算 Δ/Δ%，避免依賴單一欄位。
- rows/head_dates/tail_dates 用於快速偵測抓錯頁、資料斷裂或頁面改版。
- roll25 區塊只讀取 repo 內既有 JSON（confirm-only），不在此 workflow 內重抓資料。
- roll25 LookbackNActual 未滿 target 時：只做『信心降級註記』，不改 margin 資料品質。

## 6) 反方審核檢查（任一 Margin 失敗 → margin_quality=PARTIAL；roll25 僅供一致性判定）
- Check-1 TWSE meta_date==series[0].date：✅（OK）
- Check-1 TPEX meta_date==series[0].date：✅（OK）
- Check-2 TWSE head5 dates 嚴格遞減且無重複：✅（OK）
- Check-2 TPEX head5 dates 嚴格遞減且無重複：✅（OK）
- Check-3 TWSE/TPEX head5 完全相同（日期+餘額）視為抓錯頁：✅（OK）
- Check-4 TWSE history rows>=21：✅（OK）（rows=32）
- Check-4 TPEX history rows>=21：✅（OK）（rows=32）
- Check-5 TWSE 20D base_date 存在於 series：✅（OK）
- Check-5 TPEX 20D base_date 存在於 series：✅（OK）
- Check-6 roll25 UsedDate 與 TWSE 最新日期一致（confirm-only）：✅（OK）
- Check-7 roll25 Lookback window（info）：⚠️（NOTE）（LookbackNActual=17/20（window 未滿 → 信心降級））

_generated_at_utc: 2026-01-26T23:40:36Z_
