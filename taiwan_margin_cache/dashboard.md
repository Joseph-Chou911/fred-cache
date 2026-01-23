# Taiwan Margin Financing Dashboard

## 1) 結論
- NA + 資料品質 PARTIAL

## 2) 資料
- 上市(TWSE)：融資餘額 NA 億元｜資料日期 NA｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg）
- 上櫃(TPEX)：融資餘額 NA 億元｜資料日期 NA｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg&no=TWOI）
- 合計：融資餘額 NA 億元｜資料日期 NA｜來源：TWSE/TPEX=NA（最新日不一致或缺值）

## 3) 計算（以 history.balance 序列計算 Δ/Δ%，不依賴站點『增加』欄）
### 上市(TWSE)
- 1D：NA 億元；NA %（基期日=NA）
- 5D：NA 億元；NA %（基期日=NA）
- 20D：NA 億元；NA %（基期日=NA）

### 上櫃(TPEX)
- 1D：NA 億元；NA %（基期日=NA）
- 5D：NA 億元；NA %（基期日=NA）
- 20D：NA 億元；NA %（基期日=NA）

### 合計(上市+上櫃)
- 1D：NA 億元；NA %（基期日=NA）
- 5D：NA 億元；NA %（基期日=NA）
- 20D：NA 億元；NA %（基期日=NA）

## 4) 稽核備註
- TWSE：len(unique_dates)=0 → 品質 PARTIAL
- TPEX：len(unique_dates)=0 → 品質 PARTIAL
- 合計僅在「最新日一致」且「基期日一致」時才計算（避免跨日錯配造成誤判）。
- history 去重鍵為 (market, data_date)，seed 只會在該 market 尚無任何歷史資料時執行一次。

_generated_at_utc: 2026-01-23T04:26:27Z_
