# Taiwan Margin Financing Dashboard

## 1) 結論
- 擴張 + 資料品質 OK

## 2) 資料
- 上市(TWSE)：融資餘額 3717.30 億元｜資料日期 2026-01-22｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg）
  - rows=30｜head_dates=['2026-01-22', '2026-01-21', '2026-01-20']｜tail_dates=['2025-12-12', '2025-12-11', '2025-12-10']
- 上櫃(TPEX)：融資餘額 1301.40 億元｜資料日期 2026-01-22｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg&no=TWOI）
  - rows=30｜head_dates=['2026-01-22', '2026-01-21', '2026-01-20']｜tail_dates=['2025-12-12', '2025-12-11', '2025-12-10']
- 合計：融資餘額 5018.70 億元｜資料日期 2026-01-22｜來源：TWSE=HiStock / TPEX=HiStock

## 3) 計算（以 balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）
### 上市(TWSE)
- 1D：Δ=39.80 億元；Δ%=1.0823 %｜latest=3717.30｜base=3677.50（基期日=2026-01-21）
- 5D：Δ=124.30 億元；Δ%=3.4595 %｜latest=3717.30｜base=3593.00（基期日=2026-01-15）
- 20D：Δ=341.40 億元；Δ%=10.1129 %｜latest=3717.30｜base=3375.90（基期日=2025-12-23）

### 上櫃(TPEX)
- 1D：Δ=9.60 億元；Δ%=0.7431 %｜latest=1301.40｜base=1291.80（基期日=2026-01-21）
- 5D：Δ=19.10 億元；Δ%=1.4895 %｜latest=1301.40｜base=1282.30（基期日=2026-01-15）
- 20D：Δ=155.60 億元；Δ%=13.5800 %｜latest=1301.40｜base=1145.80（基期日=2025-12-23）

### 合計(上市+上櫃)
- 1D：Δ=49.40 億元；Δ%=0.9941 %｜latest=5018.70｜base=4969.30（基期日=2026-01-21）
- 5D：Δ=143.40 億元；Δ%=2.9414 %｜latest=5018.70｜base=4875.30（基期日=2026-01-15）
- 20D：Δ=497.00 億元；Δ%=10.9914 %｜latest=5018.70｜base=4521.70（基期日=2025-12-23）

## 4) 稽核備註
- 合計嚴格規則：僅在『最新資料日期一致』且『該 horizon 基期日一致』時才計算合計；否則該 horizon 合計輸出 NA。
- 即使站點『融資增加(億)』欄缺失，本 dashboard 仍以 balance 序列計算 Δ/Δ%，避免依賴單一欄位。
- rows/head_dates/tail_dates 用於快速偵測抓錯頁、資料斷裂或頁面改版。

## 5) 反方審核檢查（任一失敗 → PARTIAL）
- Check-1 TWSE meta_date==series[0].date：✅（OK）
- Check-1 TPEX meta_date==series[0].date：✅（OK）
- Check-2 TWSE head5 dates 嚴格遞減且無重複：✅（OK）
- Check-2 TPEX head5 dates 嚴格遞減且無重複：✅（OK）
- Check-3 TWSE/TPEX head5 完全相同（日期+餘額）視為抓錯頁：✅（OK）
- Check-4 TWSE rows>=21：✅（OK）（rows=30）
- Check-4 TPEX rows>=21：✅（OK）（rows=30）
- Check-5 TWSE 20D base_date 存在於 series：✅（OK）
- Check-5 TPEX 20D base_date 存在於 series：✅（OK）

_generated_at_utc: 2026-01-23T06:16:14Z_
