# Taiwan Margin Financing Dashboard
## 1) 結論
- NA（以 1D 合計方向判讀；若缺市場資料則以可得者近似） + 資料品質 LOW
## 2) 資料
- 上市(TWSE)：融資餘額 3,717.34 億元；融資增減 39.89 億元（%：NA；此欄需基期才可算）｜資料日期 2026-01-22｜來源：Yahoo（https://tw.stock.yahoo.com/margin-balance/）
- 上櫃(TPEX)：融資餘額 NA 億元；融資增減 NA 億元（%：NA；此欄需基期才可算）｜資料日期 NA｜來源：Yahoo（https://tw.stock.yahoo.com/margin-balance/）
- 合計：NA（上市資料日期=2026-01-22；上櫃資料日期=NA；日期不一致或缺值，依規則不得合計）
## 3) 計算
### 上市(TWSE)
- 1D：NA 億元；NA %
- 5D：NA 億元；NA %
- 20D：NA 億元；NA %
### 上櫃(TPEX)
- 1D：NA 億元；NA %
- 5D：NA 億元；NA %
- 20D：NA 億元；NA %
### 合計(上市+上櫃)
- 1D：NA
- 5D：NA
- 20D：NA
## 4) 主要觸發原因
- 若出現 403/解析失敗：多半為站點反爬/前端載入導致無法取得歷史表。
- 若 5D/20D 為 NA：代表 history 交易日筆數不足（未滿 6/21 筆）。
- 若合計為 NA：上市與上櫃資料日期不一致，依你的防誤判規則禁止合計。
## 5) 下一步觀察重點
- 先把來源穩定下來：優先確保 TWSE/TPEX 都能穩定抓到 >=21 交易日，再談 z60/p60 等統計。
- 若 WantGoo 長期 403：建議直接移除 WantGoo 或改成“只做人為備援”，避免每天浪費重試時間。
- 一旦資料連續：再擴充 dashboard 加入 z60/p60/zΔ60/pΔ60（基於 history 交易日序列），並加上異常門檻通知。
