# 0050 Forward Return Conditional Report

- renderer_fingerprint: `render_tw0050_forward_return_conditional_report@2026-02-21.v1`
- input_json: `forward_return_conditional.json`
- input_generated_at_utc: `2026-02-21T13:19:50Z`
- input_build_script_fingerprint: `build_tw0050_forward_return_conditional@2026-02-21.v7`
- decision_mode: `clean_only`
- scheme: `bb_z_5bucket_v1`
- bb_window,k,ddof: `60`, `2.0`, `0`

## Meta
- generated_at_utc: `2026-02-21T13:19:50Z`
- build_script_fingerprint: `build_tw0050_forward_return_conditional@2026-02-21.v7`
- cache_dir: `tw0050_bb_cache`
- price_calc: `adjclose`
- stats_last_date: `2026-02-11`
- price_last_date: `2026-02-11`
- rows_price_csv: `4192`
- price_csv: `data.csv`
- stats_json: `stats_latest.json`
- out_json: `forward_return_conditional.json`
- stats_path: `tw0050_bb_cache/stats_latest.json`
- stats_build_fingerprint: `tw0050_bb60_k2_forwardmdd20@2026-02-21.v12.adjclose_audit`
- stats_generated_at_utc: `2026-02-21T11:56:58Z`

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

### break_samples (first up to 5)
| idx | break_date | prev_date | prev_price | price | ratio |
| --- | --- | --- | --- | --- | --- |
| 1238 | 2014-01-02 | 2013-12-31 | 37.412415 | 9.329201 | 0.249361097289 |

## Current
- asof_date: `2026-02-11`
- current_bb_z: `2.054269`
- current_bucket_key: `z_ge_2.0`
- current_bucket_canonical: `>=2`

## Horizon 10D

- excluded_by_break_mask: `10`

### CLEAN
_Primary for interpretation (per policy)._
- definition: `scheme=bb_z_5bucket_v1; horizon=10D; mode=clean`
- n_total: `4113`

| bucket | n | hit_rate | p90 | p50 | p25 | p10 | p05 | min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | 53.66% | 5.79% | 0.50% | -2.33% | -4.71% | -6.13% | -17.53% |
| (-2,-1.5] | 205 | 60.98% | 5.87% | 1.42% | -2.20% | -4.64% | -7.66% | -20.00% |
| (-1.5,1.5) | 2641 | 58.61% | 4.61% | 0.71% | -1.58% | -3.61% | -5.06% | -24.00% |
| [1.5,2) | 656 | 56.40% | 4.56% | 0.60% | -1.24% | -3.30% | -4.76% | -10.09% |
| >=2 | 406 | 65.02% | 4.85% | 0.86% | -0.59% | -2.02% | -2.83% | -10.47% |

### CLEAN — min_audit_by_bucket
| bucket | n | min | entry_date | entry_price | future_date | future_price |
| --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | -17.53% | 2020-03-09 | 18.100203 | 2020-03-23 | 14.927133 |
| (-2,-1.5] | 205 | -20.00% | 2025-03-24 | 44.736397 | 2025-04-09 | 35.789116 |
| (-1.5,1.5) | 2641 | -24.00% | 2020-03-05 | 19.017332 | 2020-03-19 | 14.452755 |
| [1.5,2) | 656 | -10.09% | 2009-06-03 | 29.758421 | 2009-06-17 | 26.757057 |
| >=2 | 406 | -10.47% | 2024-07-11 | 48.706791 | 2024-07-29 | 43.607380 |

### RAW
_Audit-only._
- definition: `scheme=bb_z_5bucket_v1; horizon=10D; mode=raw`
- n_total: `4123`

| bucket | n | hit_rate | p90 | p50 | p25 | p10 | p05 | min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | 53.66% | 5.79% | 0.50% | -2.33% | -4.71% | -6.13% | -17.53% |
| (-2,-1.5] | 205 | 60.98% | 5.87% | 1.42% | -2.20% | -4.64% | -7.66% | -20.00% |
| (-1.5,1.5) | 2648 | 58.46% | 4.61% | 0.70% | -1.61% | -3.66% | -5.11% | -75.13% |
| [1.5,2) | 657 | 56.32% | 4.56% | 0.59% | -1.24% | -3.32% | -4.82% | -75.17% |
| >=2 | 408 | 64.71% | 4.84% | 0.85% | -0.63% | -2.06% | -3.15% | -75.43% |

### RAW — min_audit_by_bucket
| bucket | n | min | entry_date | entry_price | future_date | future_price |
| --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | -17.53% | 2020-03-09 | 18.100203 | 2020-03-23 | 14.927133 |
| (-2,-1.5] | 205 | -20.00% | 2025-03-24 | 44.736397 | 2025-04-09 | 35.789116 |
| (-1.5,1.5) | 2648 | -75.13% | 2013-12-25 | 36.870659 | 2014-01-09 | 9.169865 |
| [1.5,2) | 657 | -75.17% | 2013-12-27 | 37.157471 | 2014-01-13 | 9.225631 |
| >=2 | 408 | -75.43% | 2013-12-30 | 37.476147 | 2014-01-14 | 9.209698 |

### excluded_entries_sample (first up to 5)

| entry_idx | entry_date | entry_price | first_break_idx | first_break_date | break_ratio |
| --- | --- | --- | --- | --- | --- |
| 1228 | 2013-12-18 | 36.328915 | 1238 | 2014-01-02 | 0.249361097289 |
| 1229 | 2013-12-19 | 36.551987 | 1238 | 2014-01-02 | 0.249361097289 |
| 1230 | 2013-12-20 | 36.615723 | 1238 | 2014-01-02 | 0.249361097289 |
| 1231 | 2013-12-23 | 36.870659 | 1238 | 2014-01-02 | 0.249361097289 |
| 1232 | 2013-12-24 | 36.838791 | 1238 | 2014-01-02 | 0.249361097289 |

## Horizon 20D

- excluded_by_break_mask: `20`

### CLEAN
_Primary for interpretation (per policy)._
- definition: `scheme=bb_z_5bucket_v1; horizon=20D; mode=clean`
- n_total: `4093`

| bucket | n | hit_rate | p90 | p50 | p25 | p10 | p05 | min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | 61.46% | 8.45% | 1.12% | -2.77% | -6.07% | -9.91% | -21.08% |
| (-2,-1.5] | 205 | 65.85% | 10.31% | 2.84% | -1.29% | -6.30% | -8.34% | -14.76% |
| (-1.5,1.5) | 2632 | 62.20% | 7.00% | 1.54% | -1.90% | -5.11% | -7.30% | -25.57% |
| [1.5,2) | 655 | 54.50% | 6.87% | 0.43% | -1.83% | -4.30% | -5.55% | -12.22% |
| >=2 | 396 | 69.70% | 9.25% | 1.84% | -0.51% | -3.79% | -5.16% | -17.11% |

### CLEAN — min_audit_by_bucket
| bucket | n | min | entry_date | entry_price | future_date | future_price |
| --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | -21.08% | 2025-03-10 | 45.348385 | 2025-04-09 | 35.789116 |
| (-2,-1.5] | 205 | -14.76% | 2025-03-21 | 44.785355 | 2025-04-22 | 38.175873 |
| (-1.5,1.5) | 2632 | -25.57% | 2020-02-19 | 19.417919 | 2020-03-19 | 14.452755 |
| [1.5,2) | 655 | -12.22% | 2024-07-05 | 46.076267 | 2024-08-06 | 40.444271 |
| >=2 | 396 | -17.11% | 2024-07-04 | 46.244427 | 2024-08-05 | 38.331509 |

### RAW
_Audit-only._
- definition: `scheme=bb_z_5bucket_v1; horizon=20D; mode=raw`
- n_total: `4113`

| bucket | n | hit_rate | p90 | p50 | p25 | p10 | p05 | min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | 61.46% | 8.45% | 1.12% | -2.77% | -6.07% | -9.91% | -21.08% |
| (-2,-1.5] | 205 | 65.85% | 10.31% | 2.84% | -1.29% | -6.30% | -8.34% | -14.76% |
| (-1.5,1.5) | 2648 | 61.82% | 6.95% | 1.52% | -1.97% | -5.28% | -7.54% | -75.00% |
| [1.5,2) | 657 | 54.34% | 6.86% | 0.42% | -1.83% | -4.36% | -5.60% | -75.30% |
| >=2 | 398 | 69.35% | 9.24% | 1.83% | -0.67% | -3.86% | -5.65% | -76.28% |

### RAW — min_audit_by_bucket
| bucket | n | min | entry_date | entry_price | future_date | future_price |
| --- | --- | --- | --- | --- | --- | --- |
| <=-2 | 205 | -21.08% | 2025-03-10 | 45.348385 | 2025-04-09 | 35.789116 |
| (-2,-1.5] | 205 | -14.76% | 2025-03-21 | 44.785355 | 2025-04-22 | 38.175873 |
| (-1.5,1.5) | 2648 | -75.00% | 2013-12-10 | 36.838791 | 2014-01-08 | 9.209698 |
| [1.5,2) | 657 | -75.30% | 2013-12-27 | 37.157471 | 2014-01-27 | 9.177831 |
| >=2 | 398 | -76.28% | 2013-12-30 | 37.476147 | 2014-02-05 | 8.891022 |

### excluded_entries_sample (first up to 5)

| entry_idx | entry_date | entry_price | first_break_idx | first_break_date | break_ratio |
| --- | --- | --- | --- | --- | --- |
| 1218 | 2013-12-04 | 36.615723 | 1238 | 2014-01-02 | 0.249361097289 |
| 1219 | 2013-12-05 | 36.392643 | 1238 | 2014-01-02 | 0.249361097289 |
| 1220 | 2013-12-06 | 36.424519 | 1238 | 2014-01-02 | 0.249361097289 |
| 1221 | 2013-12-09 | 36.743195 | 1238 | 2014-01-02 | 0.249361097289 |
| 1222 | 2013-12-10 | 36.838791 | 1238 | 2014-01-02 | 0.249361097289 |

## Alignment hints (optional)
- stats_last_date (from stats_json): `2026-02-11`
- stats_last_date (recorded in forward_return_conditional.json): `2026-02-11`
- price_last_date (from forward_return_conditional.json): `2026-02-11`
- current.asof_date (from forward_return_conditional.json): `2026-02-11`
- notes: (no obvious mismatches detected)
