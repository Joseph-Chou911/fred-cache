# Taiwan Margin Financing Dashboard

## 1) 結論
- NA + 資料品質 LOW

## 2) 資料
- 上市(TWSE)：融資餘額 NA 億元；融資增減 NA 億元（%：NA）｜資料日期 NA｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg）
- 上櫃(TPEX)：融資餘額 NA 億元；融資增減 NA 億元（%：NA）｜資料日期 NA｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg&no=TWOI）
- 合計：NA（上市資料日期=NA；上櫃資料日期=NA；日期不一致或缺值，依規則不得合計）

## 3) 計算
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

## 4) 主要觸發原因
- Yahoo/WantGoo 常見 JS/403 或反爬，會導致抓取不穩；Scheme2 以 HiStock 優先降低失敗率。
- 合計嚴格規則：只要上市/上櫃最新日或基期日不一致，就不計算合計（避免跨日錯配）。
- 5D/20D 若為 NA：代表該市場 rows 不足（<6 / <21）或基期缺值，依規則不補猜。

## 5) 下一步觀察重點
- 先確保 TWSE/TPEX 都能穩定抓到 >=21 交易日，再往 z60/p60/zΔ60/pΔ60 擴充，避免斷資料假訊號。
- 若未來要回到 Yahoo/WantGoo：必須保留『市場識別驗證』與『TPEX≠TWSE』防呆，否則很容易誤判。
- 若 HiStock 偶發失敗，可再加一個“官方 OpenData”備援，但要把資料品質降級為 PARTIAL 並在資料段標示。

_generated_at_utc: 2026-01-23T03:11:29Z_
