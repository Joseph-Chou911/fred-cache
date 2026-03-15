# NAV SEC Pipeline Report

## Summary
- generated_at_utc: `2026-03-15T15:01:00Z`
- script: `nav_sec_pipeline.py`
- script_version: `v1.0.1`
- coverage_total: `5`
- coverage_usable: `3`
- coverage_fresh: `3`
- coverage_all_with_pd: `5`
- nav_fresh_max_days: `150`
- median_discount_pct_usable: `-12.147103`
- median_discount_pct_all_rows: `-26.063471`
- median_discount_pct_fresh: `-12.147103`
- confidence: `PARTIAL`

## Interpretation Notes
- `median_discount_pct_usable`: median using only rows with `used_in_stats=true`
- `median_discount_pct_all_rows`: median using all rows that have a calculable premium/discount, even if DQ marked them as review/excluded
- `median_discount_pct_fresh`: median using rows with `fresh_for_rule=true`

## SEC Fetch Meta
- ticker_map_ok: `True`

## Rows

| ticker | source | method | nav | nav_date | report_date | market_price_date | market_close | premium_discount_pct | dq_status | used_in_stats | fresh_for_rule | review_flags | snippet |
|---|---|---|---:|---|---|---|---:|---:|---|---|---|---|---|
| ARCC | sec_xbrl | xbrl_companyconcept | 19.94 | 2025-12-31 | 2026-03-15 | 2026-03-13 | 17.860001 | -10.431289 | OK | True | True |  | us-gaap:NetAssetValuePerShare unit=USD/shares |
| BXSL | sec_xbrl | xbrl_companyconcept | 26.92 | 2025-12-31 | 2026-03-15 | 2026-03-13 | 23.65 | -12.147103 | OK | True | True |  | us-gaap:NetAssetValuePerShare unit=USD/shares |
| FSK | sec_xbrl | xbrl_companyconcept | 20.89 | 2025-12-31 | 2026-03-15 | 2026-03-13 | 10.09 | -51.699378 | REVIEW_DISCOUNT_TOO_DEEP | False | False |  | us-gaap:NetAssetValuePerShare unit=USD/shares |
| OBDC | sec_xbrl | xbrl_companyconcept | 14.81 | 2025-12-31 | 2026-03-15 | 2026-03-13 | 10.95 | -26.063471 | OK | True | True |  | us-gaap:NetAssetValuePerShare unit=USD/shares |
| PSEC | sec_xbrl | xbrl_companyconcept | 6.21 | 2025-12-31 | 2026-03-15 | 2026-03-13 | 2.56 | -58.776167 | REVIEW_DISCOUNT_TOO_DEEP | False | False |  | us-gaap:NetAssetValuePerShare unit=USD/shares |

## Detailed Rows (JSON preview)

```json
[
  {
    "ticker": "ARCC",
    "source": "sec_xbrl",
    "method": "xbrl_companyconcept",
    "nav": 19.94,
    "filing_date": "2026-02-04",
    "nav_date": "2025-12-31",
    "date_source": "xbrl_end",
    "match_score": 100.0,
    "snippet": "us-gaap:NetAssetValuePerShare unit=USD/shares",
    "accession_no": null,
    "form": null,
    "doc_name": null,
    "doc_url": null,
    "xbrl_taxonomy": "us-gaap",
    "xbrl_concept": "NetAssetValuePerShare",
    "price_obs_date": null,
    "price_obs_close": null,
    "implied_side": null,
    "implied_pct": null,
    "review_flags": [],
    "notes": [
      "unit=USD/shares"
    ],
    "cik": "1287750",
    "report_date": "2026-03-15",
    "market_date": "2026-03-15",
    "market_price_date": "2026-03-13",
    "market_close": 17.860001,
    "market_price_status": "ok",
    "premium_discount_pct": -10.431289,
    "nav_age_days": 74,
    "dq_status": "OK",
    "used_in_stats": true,
    "fresh_for_rule": true
  },
  {
    "ticker": "BXSL",
    "source": "sec_xbrl",
    "method": "xbrl_companyconcept",
    "nav": 26.92,
    "filing_date": "2026-02-25",
    "nav_date": "2025-12-31",
    "date_source": "xbrl_end",
    "match_score": 100.0,
    "snippet": "us-gaap:NetAssetValuePerShare unit=USD/shares",
    "accession_no": null,
    "form": null,
    "doc_name": null,
    "doc_url": null,
    "xbrl_taxonomy": "us-gaap",
    "xbrl_concept": "NetAssetValuePerShare",
    "price_obs_date": null,
    "price_obs_close": null,
    "implied_side": null,
    "implied_pct": null,
    "review_flags": [],
    "notes": [
      "unit=USD/shares"
    ],
    "cik": "1736035",
    "report_date": "2026-03-15",
    "market_date": "2026-03-15",
    "market_price_date": "2026-03-13",
    "market_close": 23.65,
    "market_price_status": "ok",
    "premium_discount_pct": -12.147103,
    "nav_age_days": 74,
    "dq_status": "OK",
    "used_in_stats": true,
    "fresh_for_rule": true
  },
  {
    "ticker": "FSK",
    "source": "sec_xbrl",
    "method": "xbrl_companyconcept",
    "nav": 20.89,
    "filing_date": "2026-02-25",
    "nav_date": "2025-12-31",
    "date_source": "xbrl_end",
    "match_score": 100.0,
    "snippet": "us-gaap:NetAssetValuePerShare unit=USD/shares",
    "accession_no": null,
    "form": null,
    "doc_name": null,
    "doc_url": null,
    "xbrl_taxonomy": "us-gaap",
    "xbrl_concept": "NetAssetValuePerShare",
    "price_obs_date": null,
    "price_obs_close": null,
    "implied_side": null,
    "implied_pct": null,
    "review_flags": [],
    "notes": [
      "unit=USD/shares",
      "deep_discount_preserved_for_review_high_confidence_xbrl"
    ],
    "cik": "1422183",
    "report_date": "2026-03-15",
    "market_date": "2026-03-15",
    "market_price_date": "2026-03-13",
    "market_close": 10.09,
    "market_price_status": "ok",
    "premium_discount_pct": -51.699378,
    "nav_age_days": 74,
    "dq_status": "REVIEW_DISCOUNT_TOO_DEEP",
    "used_in_stats": false,
    "fresh_for_rule": false
  },
  {
    "ticker": "OBDC",
    "source": "sec_xbrl",
    "method": "xbrl_companyconcept",
    "nav": 14.81,
    "filing_date": "2026-02-18",
    "nav_date": "2025-12-31",
    "date_source": "xbrl_end",
    "match_score": 100.0,
    "snippet": "us-gaap:NetAssetValuePerShare unit=USD/shares",
    "accession_no": null,
    "form": null,
    "doc_name": null,
    "doc_url": null,
    "xbrl_taxonomy": "us-gaap",
    "xbrl_concept": "NetAssetValuePerShare",
    "price_obs_date": null,
    "price_obs_close": null,
    "implied_side": null,
    "implied_pct": null,
    "review_flags": [],
    "notes": [
      "unit=USD/shares"
    ],
    "cik": "1655888",
    "report_date": "2026-03-15",
    "market_date": "2026-03-15",
    "market_price_date": "2026-03-13",
    "market_close": 10.95,
    "market_price_status": "ok",
    "premium_discount_pct": -26.063471,
    "nav_age_days": 74,
    "dq_status": "OK",
    "used_in_stats": true,
    "fresh_for_rule": true
  },
  {
    "ticker": "PSEC",
    "source": "sec_xbrl",
    "method": "xbrl_companyconcept",
    "nav": 6.21,
    "filing_date": "2026-02-09",
    "nav_date": "2025-12-31",
    "date_source": "xbrl_end",
    "match_score": 100.0,
    "snippet": "us-gaap:NetAssetValuePerShare unit=USD/shares",
    "accession_no": null,
    "form": null,
    "doc_name": null,
    "doc_url": null,
    "xbrl_taxonomy": "us-gaap",
    "xbrl_concept": "NetAssetValuePerShare",
    "price_obs_date": null,
    "price_obs_close": null,
    "implied_side": null,
    "implied_pct": null,
    "review_flags": [],
    "notes": [
      "unit=USD/shares",
      "deep_discount_preserved_for_review_high_confidence_xbrl"
    ],
    "cik": "1287032",
    "report_date": "2026-03-15",
    "market_date": "2026-03-15",
    "market_price_date": "2026-03-13",
    "market_close": 2.56,
    "market_price_status": "ok",
    "premium_discount_pct": -58.776167,
    "nav_age_days": 74,
    "dq_status": "REVIEW_DISCOUNT_TOO_DEEP",
    "used_in_stats": false,
    "fresh_for_rule": false
  }
]
```
