# TWSE Roll25 (Turnover) Report

## 1) Audit Header
- source_latest_report: `roll25_cache/latest_report.json`
- source_stats_latest: `roll25_cache/stats_latest.json`
- latest_report.generated_at: `2026-01-27T18:26:04.016678+08:00`
- timezone: `Asia/Taipei`
- UsedDate (data date): `2026-01-26`
- run_day_tag (from latest_report): `WEEKDAY`
- used_date_status: `DATA_NOT_UPDATED`

## 2) Summary (from latest_report)
- `今日資料未更新；UsedDate=2026-01-26：Mode=FULL；freshness_ok=True；daily endpoint has not published today's row yet`

## 3) 成交量狀況（可讀版）
- Turnover (TradeValue, TWD): `747,339,306,040`
- vol_multiplier (20D avg): `1.027`
- vol_threshold: `1.500`
- signals.VolumeAmplified: `false`

### 3.1 判斷邏輯（固定規則、無猜測）
- 依倍數判讀：vol_multiplier=1.027 < 1.500 → **未達放量門檻**
- 位階參考（TradeValue）：60D z=1.160, p=79.2; 252D z=2.222, p=95.0

## 4) 價格/波動概況
- Close: `32064.52`
- PctChange (D vs D-1): `0.322%`
- AmplitudePct (High-Low vs prev close): `0.647%`
- signals.DownDay: `false`

## 5) 市場行為 Signals（供 cross_module / heated_market 用）
- signals.NewLow_N: `0`
- signals.ConsecutiveBreak: `0`

> 解讀提醒：NewLow_N=0 表示未創近 N 日新低；ConsecutiveBreak=0 表示未出現連續下跌（日報酬<0）延伸。

## 6) Data Quality / Confidence 線索
- ohlc_status: `OK`
- signals.OhlcMissing: `false`
- freshness_ok: `true`
- freshness_age_days: `1`
- mode: `FULL`
- LookbackNActual/Target: `20/20`

## 7) TradeValue 位階（stats_latest.json）
- asof: `2026-01-26`
- 60D: value=747339306040.000, z=1.160, p=79.2, n=60/60
- 252D: value=747339306040.000, z=2.222, p=95.0, n=252/252
- points_total_available(trade_value): `275`

## 8) Notes (deterministic)
- 本報告不含任何 runtime timestamp，僅以 latest_report.generated_at 代表資料版本。
- 本報告僅做可讀化彙整，不改變 roll25_cache 的任何運算結果。
