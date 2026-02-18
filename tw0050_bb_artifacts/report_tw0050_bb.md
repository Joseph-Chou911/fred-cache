# TW0050 BB Monitor Report (BB(60,2.0) + forward_mdd(20D))

- report_generated_at_utc: `2026-02-18T16:40:37Z`
- symbol: `0050.TW`
- as_of_date: `2026-02-11`
- data_source: `yfinance` | price_basis: `Adj Close` | bb_base: `price`
- script_fingerprint: `6b3f0011ae5f`
- data_age_days(local): 8 | fetch_ok: `True` | insufficient_history: `False`

## 15秒摘要

- **0050.TW** (as_of=2026-02-11 price=77.2000) → **ABOVE_UPPER_BAND** (reason=z>=2.0); z=2.054, pos=1.014, dist_to_lower=27.60%, dist_to_upper=-0.37%
- forward_mdd(20D) cond(z<=-1.5): n=410, p50=-2.81%, p10=-10.46%, min=-22.67% (conf=HIGH)

## 指標明細

| item | value |
|---|---:|
| price | 77.2000 |
| sma(60) | 66.4043 |
| std(60, ddof=0) | 5.255237 |
| upper | 76.9148 |
| lower | 55.8939 |
| z | 2.054 |
| position_in_band | 1.014 |
| dist_to_lower | 27.60% |
| dist_to_upper | -0.37% |

## forward_mdd 定義與分佈

- 定義：`min(0, min_{i=1..H} (price[t+i]/price[t]-1)), H=horizon trading days`

### 全樣本（不分 z）

- n=4172, p50=-1.85%, p10=-7.02%, min=-76.28% (conf=HIGH)

### 條件樣本（z <= -1.5）

- n=410, p50=-2.81%, p10=-10.46%, min=-22.67% (conf=HIGH)

## 資料品質提醒（務實版）

- 資料可能偏舊：local age=8 天（若遇到連假/週末，屬合理現象）。

## Repro

```bash
python /home/runner/work/fred-cache/fred-cache/scripts/tw0050_bb_len60_k2_forwardmdd.py --symbol 0050.TW --window 60 --k 2.0 --horizon 20 --z_threshold -1.5 --cache_dir tw0050_bb_artifacts --use_adj_close
```
