# Taiwan Margin Financing Dashboard

## 1) 結論
- NA + 資料品質 PARTIAL

## 2) 資料
- 上市(TWSE)：融資餘額 3717.30 億元；融資增減 39.90 億元（%：NA）｜資料日期 2026-01-22｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg）
- 上櫃(TPEX)：融資餘額 1301.40 億元；融資增減 9.60 億元（%：NA）｜資料日期 2026-01-22｜來源：HiStock（https://histock.tw/stock/three.aspx?m=mg&no=TWOI）
- 合計：融資餘額 5018.70 億元；融資增減 49.50 億元（%：NA）｜資料日期 2026-01-22｜來源：TWSE=HiStock / TPEX=HiStock

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
- 若出現 NA：通常是來源頁面改版/反爬，或交易日列數不足（<6 / <21），或 history 缺該市場。
- 合計嚴格規則：僅在 TWSE 與 TPEX 最新資料日期一致時才允許合計；且各 horizon 基期日需一致，否則該 horizon 合計輸出 NA。
- 若出現 TWSE/TPEX 數列異常相同：高機率抓錯頁面或市場識別失敗，應立即降級或停用該來源。

## 5) 下一步觀察重點
- 先確保 TWSE/TPEX 兩市場都能穩定連續抓到 >=21 交易日（才有資格維持 OK）。
- 若未來加入 z60/p60/zΔ60/pΔ60：務必基於「交易日序列」且缺值不補，否則容易產生假訊號。
- 若你要做泡沫監控：建議再加「融資餘額/成交金額」或「融資餘額/市值」類的比值指標，單看餘額容易受盤勢規模放大影響。

_generated_at_utc: 2026-01-23T02:34:37Z_
