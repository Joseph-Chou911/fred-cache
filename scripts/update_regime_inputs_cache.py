name: Update regime inputs cache

on:
  workflow_dispatch: {}
  schedule:
    - cron: "30 0 * * *"  # 00:30 UTC = 08:30 Asia/Taipei

permissions:
  contents: write

concurrency:
  group: repo-writer-main
  cancel-in-progress: false

jobs:
  update:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        shell: bash
        run: |
          set -euo pipefail
          python -m pip install --upgrade pip

      # NEW: snapshot previous counts (baseline) BEFORE updater runs
      - name: Snapshot previous history counts (baseline)
        shell: bash
        run: |
          set -euo pipefail
          python - << 'PY'
          import json, os, math
          from collections import defaultdict

          p = "regime_inputs_cache/inputs_history_lite.json"
          out = "/tmp/prev_counts.json"
          if not os.path.exists(p):
            with open(out, "w", encoding="utf-8") as f:
              json.dump({}, f)
            print("baseline: no previous history file")
            raise SystemExit(0)

          obj = json.load(open(p, "r", encoding="utf-8"))
          c = defaultdict(int)
          def f(x):
            try:
              s = str(x).strip()
              if s == "" or s.upper()=="NA": return None
              return float(s)
            except: return None

          for r in obj if isinstance(obj, list) else []:
            sid = (r.get("series_id") or "").strip()
            dd  = (r.get("data_date") or "").strip()
            v = f(r.get("value"))
            if sid and dd and v is not None:
              c[sid] += 1

          with open(out, "w", encoding="utf-8") as f:
            json.dump(dict(c), f, ensure_ascii=False, indent=2)
          print(f"baseline written: {out}")
          PY

      - name: Run updater (serial, auditable)
        shell: bash
        run: |
          set -euo pipefail
          python scripts/update_regime_inputs_cache.py

      # NEW: postprocess (write-back history + compute MA60/MA252 features + shrink check)
      - name: Postprocess: enforce history + compute MA60/MA252 features
        shell: bash
        run: |
          set -euo pipefail
          python scripts/postprocess_regime_inputs_features.py \
            --write-back-history \
            --counts-in /tmp/prev_counts.json \
            --shrink-hard-fail

      - name: Compatibility copies (scheme A)
        shell: bash
        run: |
          set -euo pipefail
          cp -f regime_inputs_cache/inputs_latest.json regime_inputs_cache/latest.json
          cp -f regime_inputs_cache/inputs_history_lite.json regime_inputs_cache/history_lite.json

      - name: "Patch manifest (scheme A: pin both canonical+compat)"
        shell: bash
        run: |
          set -euo pipefail
          python scripts/patch_manifest_regime_inputs.py --repo "Joseph-Chou911/fred-cache"

      - name: "Sanity check: required files exist & non-empty"
        shell: bash
        run: |
          set -euo pipefail

          echo "== List regime_inputs_cache =="
          ls -al regime_inputs_cache || true

          required=(
            "regime_inputs_cache/inputs_latest.json"
            "regime_inputs_cache/inputs_history_lite.json"
            "regime_inputs_cache/features_latest.json"
            "regime_inputs_cache/dq_state.json"
            "regime_inputs_cache/inputs_schema_out.json"
            "regime_inputs_cache/latest.json"
            "regime_inputs_cache/history_lite.json"
            "regime_inputs_cache/manifest.json"
          )

          echo "== Check required files (must exist and size > 0) =="
          missing=0
          for f in "${required[@]}"; do
            if [ ! -s "$f" ]; then
              echo "MISSING_OR_EMPTY: $f"
              missing=1
            else
              echo "OK: $f (size=$(wc -c < "$f"))"
            fi
          done

          if [ "$missing" -ne 0 ]; then
            echo "ERROR: required output files missing/empty. Abort."
            exit 2
          fi

      - name: "Sanity check: manifest pinned keys (scheme A)"
        shell: bash
        run: |
          set -euo pipefail
          python - << 'PY'
          import json
          from pathlib import Path

          p = Path("regime_inputs_cache/manifest.json")
          obj = json.loads(p.read_text(encoding="utf-8"))
          pinned = obj.get("pinned", {}) or {}

          required_keys = [
              "inputs_latest_json",
              "inputs_history_lite_json",
              "features_latest_json",
              "dq_state_json",
              "inputs_schema_out_json",
              "latest_json",
              "history_lite_json",
          ]

          missing = [k for k in required_keys if not pinned.get(k)]
          print("== manifest.json pinned keys ==")
          for k in required_keys:
              print(f"{k}: {pinned.get(k)}")

          if missing:
              raise SystemExit(f"ERROR: manifest pinned missing keys: {missing}")
          print("OK: manifest pinned keys present.")
          PY

      - name: Commit & push
        shell: bash
        run: |
          set -euo pipefail

          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

          git add \
            regime_inputs_cache/inputs_latest.json \
            regime_inputs_cache/inputs_history_lite.json \
            regime_inputs_cache/features_latest.json \
            regime_inputs_cache/dq_state.json \
            regime_inputs_cache/inputs_schema_out.json \
            regime_inputs_cache/latest.json \
            regime_inputs_cache/history_lite.json \
            regime_inputs_cache/manifest.json

          if git diff --cached --quiet; then
            echo "No changes to commit."
            exit 0
          fi

          git commit -m "Update regime_inputs_cache (inputs+features+manifest)"
          git push