# Taiwan Margin-Financing Dashboard（方案B）

## 1) 結論
- 融資呈現NA；資料品質 LOW

## 2) 資料
- 上市（TWSE）資料日期：**NA**；來源：WantGoo [連結](https://www.wantgoo.com/stock/margin-trading/market-price/taiex)
  - 融資餘額（億元）：**NA**
  - 融資增減（億元、%）：**NA** 億元，**NA**%

- 上櫃（TPEX）資料日期：**NA**；來源：WantGoo/Official [連結](https://www.wantgoo.com/stock/margin-trading/market-price/otc;https://www.wantgoo.com/stock/margin-trading/market-price/gtsm;https://www.wantgoo.com/stock/margin-trading/market-price/tpex)
  - 融資餘額（億元）：**NA**
  - 融資增減（億元、%）：**NA** 億元，**NA**%

- 合計（上市+上櫃）：**NA**（上市與上櫃最新資料日期不同，依規則不計算合計）

## 3) 計算
- 百分比定義＝變化(億元)/基期餘額(億元)*100；5D/20D 基期＝往回第 5/第 20 個交易日（列序）。

### 上市（TWSE）
- 1D：NA 億元，NA%
- 5D：NA 億元，NA%
- 20D：NA 億元，NA%

### 上櫃（TPEX）
- 1D：NA 億元，NA%
- 5D：NA 億元，NA%
- 20D：NA 億元，NA%

### 合計（上市+上櫃）
- 1D：NA 億元，NA%
- 5D：NA 億元，NA%
- 20D：NA 億元，NA%

## 4) 主要觸發原因
- 上市（TWSE）1D 融資增減無法計算（資料不足或缺值）。
- 上櫃（TPEX）1D 融資增減無法計算（資料不足或缺值）。
- 上市資料日期=NA、上櫃資料日期=NA 不一致 → 合計欄位依規則輸出 NA。

## 5) 下一步觀察重點
- 確認下一交易日兩市場資料日期是否同步（若不同步，合計仍需維持 NA，避免誤判）。
- 觀察 5D/20D 是否由 NA 轉為可計算（代表歷史列數補齊到足夠交易日）。
- 若 1D 與 5D 同向且幅度擴大，再把它當成「槓桿情緒變化」訊號進一步對照成交額/波動指標。

## 附註（資料擷取/降級紀錄）
- 上市（TWSE）：
  - HTTP 取得失敗：HTTPError: 403 Client Error: Forbidden for url: https://www.wantgoo.com/stock/margin-trading/market-price/taiex
  - 降級：WantGoo 不足以提供 min_rows；改用官方來源。
  - 官方 TWSE 端點嘗試失敗或無法可靠解析合計融資餘額（可能 API/欄位已變更）。
- 上櫃（TPEX）：
  - WantGoo(猜測URL)與官方來源皆無法可靠取得。
  - 官方 TPEX 端點嘗試失敗或無法可靠解析合計融資餘額（可能 CSV 格式/欄位已變更）。
