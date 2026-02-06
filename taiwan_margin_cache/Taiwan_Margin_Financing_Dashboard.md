# Taiwan Margin Financing Dashboard

## 1) 結論
- 狀態：擴張｜信號：INFO｜資料品質：OK
  - rationale: cool-down candidate: Accel<=TH and 1D%<TH (needs 2–3 consecutive confirmations)
- 上游資料狀態（latest.json）：⚠️（NOTE）（top-level confidence/fetch_status/dq_reason 未提供；不做 PASS/FAIL）
- 一致性判定（Margin × Roll25）：MARKET_SHOCK_ONLY
  - rationale: roll25 heated but Margin not heated
  - resonance_policy: latest
  - resonance_note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）
  - resonance_confidence: DOWNGRADED

## 1.1) 判定標準（本 dashboard 內建規則；顯示『實際採用門檻』）
- threshold_policy: fixed
- thresholds_used: exp20=8.0000, contr20=-8.0000, watch1d=0.8000, watch_spread20=3.0000, watch_accel=0.2500, cool_accel=0.0000, cool_1d=0.3000

### 1) WATCH（升溫）
- 條件：20D% ≥ 8.0000 且 (1D% ≥ 0.8000 或 Spread20 ≥ 3.0000 或 Accel ≥ 0.2500)
- 行動：把你其他風險模組（VIX / 信用 / 成交量）一起對照，確認是不是同向升溫。

### 2) ALERT（疑似去槓桿）
- 條件：20D% ≥ 8.0000 且 1D% < 0 且 5D% < 0
- 行動：優先看『是否出現連續負值』，因為可能開始踩踏。

### 3) 解除 WATCH（降溫）
- 條件：20D% 仍高（≥ 8.0000），但 Accel ≤ 0.0000 且 1D% < 0.3000（需連 2–3 次確認）
- 行動：代表短線槓桿加速結束，回到『擴張但不加速』。

## 1.2) 門檻校準（目標百分位 → 反推門檻值；資料不足則明確回退固定門檻）
- threshold_policy: fixed
- calib_min_n: 60
- aligned_date_intersection_rows: 40 (2026-02-05 .. 2025-12-10)
- targets (percentiles): {'pctl_expansion20': None, 'pctl_contraction20': None, 'pctl_watch1d': None, 'pctl_watchspread20': None, 'pctl_watchaccel': None, 'pctl_cool1d': None, 'pctl_coolaccel': None}
- policy=fixed：不做校準（此段僅做紀錄）

## 2) 資料
- 上市(TWSE)：融資餘額 3829.20 億元｜資料日期 2026-02-05｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg）
  - rows_latest_table=30｜rows_series=40｜head_dates=['2026-02-05', '2026-02-04', '2026-02-03']｜tail_dates=['2025-12-29', '2025-12-26', '2025-12-24']
- 上櫃(TPEX)：融資餘額 1341.10 億元｜資料日期 2026-02-05｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg&no=TWOI）
  - rows_latest_table=30｜rows_series=40｜head_dates=['2026-02-05', '2026-02-04', '2026-02-03']｜tail_dates=['2025-12-29', '2025-12-26', '2025-12-24']
- 合計：融資餘額 5170.30 億元｜資料日期 2026-02-05｜來源：TWSE=HiStock / TPEX=HiStock

## 2.0) 大盤融資維持率（proxy；僅供參考，不作為信號輸入）
- maint_path: taiwan_margin_cache/maint_ratio_latest.json
- maint_ratio_policy: PROXY_TREND_ONLY
- maint_ratio_confidence: DOWNGRADED
- data_date: 2026-02-05｜maint_ratio_pct: 178.028325
- maint_ratio_1d_delta_pctpt: -5.424351｜maint_ratio_1d_pct_change: -2.956812
- maint_ratio_trend_note: trend_from: today=178.028325(2026-02-05), prev=183.452676(2026-02-04)
- totals: financing_amount_twd=382917747000, collateral_value_twd=681702052280
- coverage: included_count=1247, missing_price_count=4
- quality: fetch_status=OK, confidence=OK, dq_reason=

## 2.0.1) 大盤融資維持率（history；display-only）
- maint_hist_path: taiwan_margin_cache/maint_ratio_history.json
- history_rows: 8
- head5: [('2026-02-05', 178.028325), ('2026-02-04', 183.452676), ('2026-02-03', 180.187892), ('2026-02-02', 178.267525), ('2026-01-30', 183.996663)]

## 2.1) 台股成交量/波動（roll25_cache；confirm-only）
- roll25_path: roll25_cache/latest_report.json
- UsedDate: 2026-02-05｜UsedDateStatus: DATA_NOT_UPDATED｜risk_level: 中(derived)（stale）｜risk_level_raw: NA｜tag: WEEKDAY
- summary: 今日資料未更新；UsedDate=2026-02-05：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet
- numbers: Close=31801.27, PctChange=-1.512985%, TradeValue=715168705076, VolumeMultiplier=0.906804, AmplitudePct=1.463496%, VolMultiplier=0.906804
- signals: DownDay=True, VolumeAmplified=False, VolAmplified=False, NewLow_N=0, ConsecutiveBreak=1, OhlcMissing=False
- action: 維持風險控管紀律；如資料延遲或 OHLC 缺失，避免做過度解讀，待資料補齊再對照完整條件。
- caveats: Sources: daily_fmtqik=https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK ; daily_mi_5mins_hist=https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
Sources: backfill_fmtqik_tpl=https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={yyyymm01} ; backfill_mi_5mins_hist_tpl=https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={yyyymm01}
run_day_tag is weekday-only heuristic (not exchange calendar)
BackfillMonths=0 | BackfillLimit=252 | StoreCap=400 | LookbackTarget=20
Mode=FULL | OHLC=OK | UsedDate=2026-02-05 | UsedDminus1=2026-02-04
RunDayTag=WEEKDAY | UsedDateStatus=DATA_NOT_UPDATED
freshness_ok=True | freshness_age_days=1
dedupe_ok=True
REPORT_CACHE_ROLL25_CAP=200 (cache_roll25 points embedded in latest_report)
ADDITIVE_DERIVED: vol_multiplier_20=today_trade_value/avg(tv_last20) (min_points=15); VolumeAmplified=(>= 1.5); NewLow_N: 60 if close<=min(close_last60) (min_points=40) else 0; ConsecutiveBreak=consecutive down days from UsedDate (ret<0) else 0/None.
ADDITIVE_UNIFIED_COMPAT: latest_report.cache_roll25 is provided (newest->oldest).
- generated_at: 2026-02-06T10:51:17.098821+08:00 (Asia/Taipei)
- resonance_confidence: DOWNGRADED

## 2.2) 一致性判定（Margin × Roll25 共振）
- 規則（deterministic，不猜）：
  1. 若 Margin∈{WATCH,ALERT} 且 roll25 heated（risk_level∈{中,高} 或 VolumeAmplified/VolAmplified/NewLow_N/ConsecutiveBreak 任一為 True）→ RESONANCE
  2. 若 Margin∈{WATCH,ALERT} 且 roll25 not heated → DIVERGENCE（槓桿端升溫，但市場面未放大）
  3. 若 Margin∉{WATCH,ALERT} 且 roll25 heated → MARKET_SHOCK_ONLY（市場面事件/波動主導）
  4. 其餘 → QUIET
- 判定：MARKET_SHOCK_ONLY（roll25 heated but Margin not heated）
- resonance_confidence: DOWNGRADED
- resonance_note: roll25 stale，但依 LATEST_AVAILABLE 政策仍使用最新可用資料判定（信心降級）

## 3) 計算（以 balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）
### 上市(TWSE)
- 1D：Δ=-11.30 億元；Δ%=-0.2942 %｜latest=3829.20｜base=3840.50（基期日=2026-02-04）
- 5D：Δ=11.40 億元；Δ%=0.2986 %｜latest=3829.20｜base=3817.80（基期日=2026-01-29）
- 20D：Δ=305.30 億元；Δ%=8.6637 %｜latest=3829.20｜base=3523.90（基期日=2026-01-08）

### 上櫃(TPEX)
- 1D：Δ=-9.90 億元；Δ%=-0.7328 %｜latest=1341.10｜base=1351.00（基期日=2026-02-04）
- 5D：Δ=-6.60 億元；Δ%=-0.4897 %｜latest=1341.10｜base=1347.70（基期日=2026-01-29）
- 20D：Δ=117.40 億元；Δ%=9.5939 %｜latest=1341.10｜base=1223.70（基期日=2026-01-08）

### 合計(上市+上櫃)
- 1D：Δ=-21.20 億元；Δ%=-0.4084 %｜latest=5170.30｜base=5191.50（基期日=2026-02-04）
- 5D：Δ=4.80 億元；Δ%=0.0929 %｜latest=5170.30｜base=5165.50（基期日=2026-01-29）
- 20D：Δ=422.70 億元；Δ%=8.9034 %｜latest=5170.30｜base=4747.60（基期日=2026-01-08）

## 4) 提前示警輔助指標（不引入外部資料）
- Accel = 1D% - (5D%/5)：-0.4269
- Spread20 = TPEX_20D% - TWSE_20D%：0.9302

## 5) 稽核備註
- 合計嚴格規則：僅在『最新資料日期一致』且『該 horizon 基期日一致』時才計算合計；否則該 horizon 合計輸出 NA。
- 即使站點『融資增加(億)』欄缺失，本 dashboard 仍以 balance 序列計算 Δ/Δ%，避免依賴單一欄位。
- rows_latest_table/head_dates/tail_dates 用於快速偵測抓錯頁、資料斷裂或頁面改版。
- rows_series 是計算輸入序列長度（由 history.json 彙整），用於 horizon 計算與 Check-4。
- roll25 區塊只讀取 repo 內既有 JSON（confirm-only），不在此 workflow 內重抓資料。
- roll25 若顯示 UsedDateStatus=DATA_NOT_UPDATED：代表資料延遲；Check-6 以 NOTE 呈現（非抓錯檔）。
- resonance_policy=latest：strict 需同日且非 stale；latest 允許 stale/date mismatch 但會 resonance_confidence=DOWNGRADED。
- maint_ratio 為 proxy（display-only）：僅看趨勢與變化（Δ），不得用 proxy 絕對水位做門檻判斷。
- threshold calibration：僅在 --threshold-policy percentile 時啟用；資料不足或未提供 target_pct 會明確回退 fixed。

## 6) 反方審核檢查（任一 Margin 失敗 → margin_quality=PARTIAL；roll25/maint/校準僅供對照）
- Check-0 latest.json top-level quality：⚠️（NOTE）（field may be absent; does not affect margin_quality）
- Check-1 TWSE meta_date==series[0].date：✅（PASS）
- Check-1 TPEX meta_date==series[0].date：✅（PASS）
- Check-2 TWSE head5 dates 嚴格遞減且無重複：✅（PASS）
- Check-2 TPEX head5 dates 嚴格遞減且無重複：✅（PASS）
- Check-3 TWSE/TPEX head5 完全相同（日期+餘額）視為抓錯頁：✅（PASS）
- Check-4 TWSE history rows>=21：✅（PASS）（rows_series=40）
- Check-4 TPEX history rows>=21：✅（PASS）（rows_series=40）
- Check-5 TWSE 20D base_date 存在於 series：✅（PASS）
- Check-5 TPEX 20D base_date 存在於 series：✅（PASS）
- Check-6 roll25 UsedDate 與 TWSE 最新日期一致（confirm-only）：⚠️（NOTE）（roll25 stale (UsedDateStatus=DATA_NOT_UPDATED) | UsedDate(2026-02-05) == TWSE(2026-02-05)）
- Check-7 roll25 Lookback window（info）：⚠️（NOTE）（skipped: roll25 stale (DATA_NOT_UPDATED)）
- Check-8 maint_ratio latest readable（info）：✅（PASS）（OK）
- Check-9 maint_ratio history readable（info）：✅（PASS）（OK）
- Check-10 maint latest vs history[0] date（info）：✅（PASS）（OK）
- Check-11 maint history head5 dates 嚴格遞減且無重複（info）：✅（PASS）（OK）
- Check-12 threshold calibration applied（info）：⚠️（NOTE）（policy=fixed）

_generated_at_utc: 2026-02-06T06:39:16Z_
