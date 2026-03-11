# 0050 Forward Return Conditional Report

- renderer_fingerprint: `render_tw0050_forward_return_conditional_report@2026-02-21.v3`
- input_json: `forward_return_conditional.json`
- input_generated_at_utc: `2026-03-11T07:32:07Z`
- input_build_script_fingerprint: `build_tw0050_forward_return_conditional@2026-02-21.v7_5`
- decision_mode: `clean_only`
- scheme: `bb_z_5bucket_v1`
- bb_window,k,ddof: `60`, `2.0`, `0`
- thresholds (near/extreme): `1.5` / `2.0`

## Meta
- generated_at_utc: `2026-03-11T07:32:07Z`
- build_script_fingerprint: `build_tw0050_forward_return_conditional@2026-02-21.v7_5`
- cache_dir: `tw0050_bb_cache`
- price_calc: `adjclose`
- stats_last_date: `2026-03-11`
- price_last_date: `2026-03-11`
- rows_price_csv: `4203`
- lookback_years: `0`
- price_csv: `data.csv`
- stats_json: `stats_latest.json`
- out_json: `forward_return_conditional.json`
- stats_path: `tw0050_bb_cache/stats_latest.json`
- bb_window_stats: `60`
- bb_k_stats: `2.0`
- stats_build_fingerprint: `tw0050_bb60_k2_forwardmdd20@2026-02-21.v12.adjclose_audit`
- stats_generated_at_utc: `2026-03-11T07:27:12Z`

## Data Quality (DQ)
- flags:
  - `RAW_MODE_HAS_SPLIT_OUTLIERS`
- notes:
  - horizon=10D excluded_by_break_mask=10
  - horizon=20D excluded_by_break_mask=20
  - raw_global_min=-0.762755 <= -0.40; treat raw as contaminated (split/outlier). Use clean_only.

## Policy
- decision_mode: `clean_only`
- raw_usable: `False`
- raw_policy: `audit_only_do_not_use`

## Break detection
- thresholds: hi=1.800000, lo=0.5555555556
- break_count_stats: `1`
- break_count_detected: `1`
- contam_mask_semantics: `exclude entries t where t < i <= t+h (t in [i-h, i-1])`

### break_samples (first up to 5)
| idx | break_date | prev_date | prev_price | price | ratio |
| --- | --- | --- | --- | --- | --- |
| 1238 | 2014-01-02 | 2013-12-31 | 37.412411 | 9.329202 | 0.249361148206 |

## Current
- asof_date: `2026-03-11`
- current_bb_z: `1.422643`
- current_bucket_key: `z_-1.5_to_1.5`
- current_bucket_canonical: `(-1.5,1.5)`

## Horizon 10D

- excluded_by_break_mask: `10`

### CLEAN
_Primary for interpretation (per policy)._
- definition: `scheme=bb_z_5bucket_v1; horizon=10D; mode=clean`
- n_total: `4124`

| bucket | n | hit_rate | p90 | p50 | p25 | p10 | p05 | min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | 53.66% | 5.79% | 0.49% | -2.33% | -4.71% | -6.13% | -17.53% |
| (-2,-1.5] | 205 | 60.98% | 5.87% | 1.42% | -2.20% | -4.64% | -7.66% | -20.00% |
| (-1.5,1.5) | 2644 | 58.66% | 4.63% | 0.72% | -1.57% | -3.61% | -5.06% | -24.00% |
| [1.5,2) | 662 | 56.80% | 4.66% | 0.64% | -1.23% | -3.29% | -4.76% | -10.09% |
| >=2 | 408 | 64.95% | 4.89% | 0.86% | -0.60% | -2.05% | -2.93% | -10.47% |

### CLEAN - min_audit_by_bucket
| bucket | n | min | entry_date | entry_price | future_date | future_price |
| --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | -17.53% | 2020-03-09 | 18.100199 | 2020-03-23 | 14.927132 |
| (-2,-1.5] | 205 | -20.00% | 2025-03-24 | 44.736397 | 2025-04-09 | 35.789116 |
| (-1.5,1.5) | 2644 | -24.00% | 2020-03-05 | 19.017332 | 2020-03-19 | 14.452751 |
| [1.5,2) | 662 | -10.09% | 2009-06-03 | 29.758429 | 2009-06-17 | 26.757051 |
| >=2 | 408 | -10.47% | 2024-07-11 | 48.706799 | 2024-07-29 | 43.607376 |

### RAW
_Audit-only._
- definition: `scheme=bb_z_5bucket_v1; horizon=10D; mode=raw`
- n_total: `4134`

| bucket | n | hit_rate | p90 | p50 | p25 | p10 | p05 | min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | 53.66% | 5.79% | 0.49% | -2.33% | -4.71% | -6.13% | -17.53% |
| (-2,-1.5] | 205 | 60.98% | 5.87% | 1.42% | -2.20% | -4.64% | -7.66% | -20.00% |
| (-1.5,1.5) | 2651 | 58.51% | 4.63% | 0.70% | -1.60% | -3.66% | -5.11% | -75.13% |
| [1.5,2) | 663 | 56.71% | 4.65% | 0.64% | -1.23% | -3.31% | -4.76% | -75.17% |
| >=2 | 410 | 64.63% | 4.89% | 0.85% | -0.64% | -2.08% | -3.26% | -75.43% |

### RAW - min_audit_by_bucket
| bucket | n | min | entry_date | entry_price | future_date | future_price |
| --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | -17.53% | 2020-03-09 | 18.100199 | 2020-03-23 | 14.927132 |
| (-2,-1.5] | 205 | -20.00% | 2025-03-24 | 44.736397 | 2025-04-09 | 35.789116 |
| (-1.5,1.5) | 2651 | -75.13% | 2013-12-25 | 36.870663 | 2014-01-09 | 9.169863 |
| [1.5,2) | 663 | -75.17% | 2013-12-27 | 37.157467 | 2014-01-13 | 9.225634 |
| >=2 | 410 | -75.43% | 2013-12-30 | 37.476139 | 2014-01-14 | 9.209700 |

### excluded_entries_sample (first up to 5)

| entry_idx | entry_date | entry_price | first_break_idx | first_break_date | break_ratio |
| --- | --- | --- | --- | --- | --- |
| 1228 | 2013-12-18 | 36.328907 | 1238 | 2014-01-02 | 0.249361148206 |
| 1229 | 2013-12-19 | 36.551983 | 1238 | 2014-01-02 | 0.249361148206 |
| 1230 | 2013-12-20 | 36.615719 | 1238 | 2014-01-02 | 0.249361148206 |
| 1231 | 2013-12-23 | 36.870663 | 1238 | 2014-01-02 | 0.249361148206 |
| 1232 | 2013-12-24 | 36.838799 | 1238 | 2014-01-02 | 0.249361148206 |

## Horizon 20D

- excluded_by_break_mask: `20`

### CLEAN
_Primary for interpretation (per policy)._
- definition: `scheme=bb_z_5bucket_v1; horizon=20D; mode=clean`
- n_total: `4104`

| bucket | n | hit_rate | p90 | p50 | p25 | p10 | p05 | min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | 61.46% | 8.45% | 1.12% | -2.77% | -6.07% | -9.91% | -21.08% |
| (-2,-1.5] | 205 | 65.85% | 10.31% | 2.84% | -1.29% | -6.30% | -8.34% | -14.76% |
| (-1.5,1.5) | 2632 | 62.20% | 7.00% | 1.54% | -1.90% | -5.11% | -7.30% | -25.57% |
| [1.5,2) | 655 | 54.50% | 6.87% | 0.43% | -1.83% | -4.30% | -5.55% | -12.22% |
| >=2 | 407 | 70.27% | 9.49% | 1.93% | -0.45% | -3.72% | -5.07% | -17.11% |

### CLEAN - min_audit_by_bucket
| bucket | n | min | entry_date | entry_price | future_date | future_price |
| --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | -21.08% | 2025-03-10 | 45.348389 | 2025-04-09 | 35.789116 |
| (-2,-1.5] | 205 | -14.76% | 2025-03-21 | 44.785355 | 2025-04-22 | 38.175873 |
| (-1.5,1.5) | 2632 | -25.57% | 2020-02-19 | 19.417923 | 2020-03-19 | 14.452751 |
| [1.5,2) | 655 | -12.22% | 2024-07-05 | 46.076271 | 2024-08-06 | 40.444271 |
| >=2 | 407 | -17.11% | 2024-07-04 | 46.244427 | 2024-08-05 | 38.331509 |

### RAW
_Audit-only._
- definition: `scheme=bb_z_5bucket_v1; horizon=20D; mode=raw`
- n_total: `4124`

| bucket | n | hit_rate | p90 | p50 | p25 | p10 | p05 | min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | 61.46% | 8.45% | 1.12% | -2.77% | -6.07% | -9.91% | -21.08% |
| (-2,-1.5] | 205 | 65.85% | 10.31% | 2.84% | -1.29% | -6.30% | -8.34% | -14.76% |
| (-1.5,1.5) | 2648 | 61.82% | 6.95% | 1.52% | -1.97% | -5.28% | -7.54% | -75.00% |
| [1.5,2) | 657 | 54.34% | 6.86% | 0.42% | -1.83% | -4.36% | -5.60% | -75.30% |
| >=2 | 409 | 69.93% | 9.48% | 1.88% | -0.49% | -3.82% | -5.49% | -76.28% |

### RAW - min_audit_by_bucket
| bucket | n | min | entry_date | entry_price | future_date | future_price |
| --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | -21.08% | 2025-03-10 | 45.348389 | 2025-04-09 | 35.789116 |
| (-2,-1.5] | 205 | -14.76% | 2025-03-21 | 44.785355 | 2025-04-22 | 38.175873 |
| (-1.5,1.5) | 2648 | -75.00% | 2013-12-10 | 36.838799 | 2014-01-08 | 9.209700 |
| [1.5,2) | 657 | -75.30% | 2013-12-27 | 37.157467 | 2014-01-27 | 9.177828 |
| >=2 | 409 | -76.28% | 2013-12-30 | 37.476139 | 2014-02-05 | 8.891024 |

### excluded_entries_sample (first up to 5)

| entry_idx | entry_date | entry_price | first_break_idx | first_break_date | break_ratio |
| --- | --- | --- | --- | --- | --- |
| 1218 | 2013-12-04 | 36.615719 | 1238 | 2014-01-02 | 0.249361148206 |
| 1219 | 2013-12-05 | 36.392654 | 1238 | 2014-01-02 | 0.249361148206 |
| 1220 | 2013-12-06 | 36.424511 | 1238 | 2014-01-02 | 0.249361148206 |
| 1221 | 2013-12-09 | 36.743191 | 1238 | 2014-01-02 | 0.249361148206 |
| 1222 | 2013-12-10 | 36.838799 | 1238 | 2014-01-02 | 0.249361148206 |

## Self-check (optional)
- enabled: `True`
### 10D
- ok: `True`
- issues: (none)
- extra (json):
```json
{
  "metrics": {
    "raw_n_total": 4134,
    "clean_n_total": 4124,
    "excluded_by_break_mask": 10,
    "clean_bucket_n_sum": 4124,
    "raw_bucket_n_sum": 4134
  },
  "eps": 1e-12
}
```
### 20D
- ok: `True`
- issues: (none)
- extra (json):
```json
{
  "metrics": {
    "raw_n_total": 4124,
    "clean_n_total": 4104,
    "excluded_by_break_mask": 20,
    "clean_bucket_n_sum": 4104,
    "raw_bucket_n_sum": 4124
  },
  "eps": 1e-12
}
```

## Alignment hints (optional)
- stats_last_date (from stats_json): `2026-03-11`
- stats_last_date (recorded in forward_return_conditional.json): `2026-03-11`
- price_last_date (from forward_return_conditional.json): `2026-03-11`
- current.asof_date (from forward_return_conditional.json): `2026-03-11`
- notes: (no obvious mismatches detected)
