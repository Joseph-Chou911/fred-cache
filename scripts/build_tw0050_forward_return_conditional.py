name: tw0050-forward-return-conditional

on:
  workflow_run:
    workflows: ["tw0050-bb60-forwardmdd20"]
    types: [completed]
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: tw0050-forward-return-conditional
  cancel-in-progress: true

jobs:
  run:
    runs-on: ubuntu-latest

    steps:
      - name: Guard (only run after success on workflow_run)
        shell: bash
        run: |
          set -euo pipefail
          if [ "${GITHUB_EVENT_NAME}" = "workflow_run" ]; then
            conclusion="$(python -c "import json; j=json.load(open('${GITHUB_EVENT_PATH}','r',encoding='utf-8')); print(j.get('workflow_run',{}).get('conclusion',''))")"
            echo "workflow_run.conclusion=${conclusion}"
            if [ "${conclusion}" != "success" ]; then
              echo "Upstream workflow not successful; skip."
              exit 0
            fi
          fi
          echo "Proceed."

      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps (minimal)
        shell: bash
        run: |
          set -euo pipefail
          python -m pip install --upgrade pip
          pip install pandas numpy

      - name: Build forward return conditional (hit-rate) — all/5y/3y
        shell: bash
        run: |
          set -euo pipefail
          set -x

          echo "=== list cache dir ==="
          ls -al tw0050_bb_cache || true
          echo "=== csv candidates ==="
          ls -al tw0050_bb_cache/*.csv || true

          # 1) pick price csv: prefer price.csv, else detect by header containing adjclose/adj_close
          PRICE_CSV="price.csv"
          if [ ! -f "tw0050_bb_cache/${PRICE_CSV}" ]; then
            PRICE_CSV=""
            for f in tw0050_bb_cache/*.csv; do
              [ -f "$f" ] || continue
              hdr="$(head -n 1 "$f" | tr 'A-Z' 'a-z' || true)"
              if echo "$hdr" | grep -Eq '(adjclose|adj_close)'; then
                PRICE_CSV="$(basename "$f")"
                break
              fi
            done
            if [ -z "${PRICE_CSV}" ]; then
              echo "ERROR: no price-like CSV found (header must contain adjclose/adj_close)."
              exit 1
            fi
            echo "Auto-detected PRICE_CSV=${PRICE_CSV}"
          fi

          # 2) required inputs
          test -f "tw0050_bb_cache/${PRICE_CSV}"
          test -f "tw0050_bb_cache/stats_latest.json"
          test -f "scripts/build_tw0050_forward_return_conditional.py"

          run_build () {
            local LOOKBACK="$1"
            local OUTNAME="$2"
            python scripts/build_tw0050_forward_return_conditional.py \
              --cache_dir tw0050_bb_cache \
              --price_csv "${PRICE_CSV}" \
              --stats_json stats_latest.json \
              --out_json "${OUTNAME}" \
              --bb_window 60 \
              --bb_k 2.0 \
              --bb_ddof 0 \
              --horizons 10,20 \
              --break_ratio_hi 1.8 \
              --break_ratio_lo 0.5555555556 \
              --lookback_years "${LOOKBACK}"
          }

          run_build 0 forward_return_conditional.json
          run_build 5 forward_return_conditional_5y.json
          run_build 3 forward_return_conditional_3y.json

      - name: Debug outputs (existence)
        shell: bash
        run: |
          set -euo pipefail
          for f in \
            tw0050_bb_cache/forward_return_conditional.json \
            tw0050_bb_cache/forward_return_conditional_5y.json \
            tw0050_bb_cache/forward_return_conditional_3y.json
          do
            echo "=== ${f} ==="
            ls -al "${f}"
            python -c "import json; j=json.load(open('${f}','r',encoding='utf-8')); print('meta.out_json:', j.get('meta',{}).get('out_json')); print('lookback_years:', j.get('meta',{}).get('lookback_years')); print('dq.flags:', j.get('dq',{}).get('flags',[]))"
          done

      - name: Render reports (all/5y/3y) — backward compatible with render v1
        shell: bash
        run: |
          set -euo pipefail
          set -x

          test -f "scripts/render_tw0050_forward_return_conditional_report.py"

          render_one () {
            local IN_JSON="$1"
            local OUT_MD="$2"

            # Preferred path: if renderer supports --input_json and --out_md, use it.
            if python scripts/render_tw0050_forward_return_conditional_report.py --help 2>/dev/null | grep -q -- "--input_json"; then
              python scripts/render_tw0050_forward_return_conditional_report.py \
                --cache_dir tw0050_bb_cache \
                --input_json "${IN_JSON}" \
                --out_md "${OUT_MD}"
              return 0
            fi

            # Fallback path for render v1 (no args):
            # - Assume it reads fixed input and writes fixed output.
            # - Use temp swap to generate multiple reports.
            local FIXED_IN="tw0050_bb_cache/forward_return_conditional.json"
            local FIXED_OUT="tw0050_bb_cache/forward_return_conditional_report.md"

            local SRC="tw0050_bb_cache/${IN_JSON}"
            local DST="${FIXED_IN}"

            local BAK_IN="tw0050_bb_cache/__bak_forward_return_conditional.json"
            local TMP_IN="tw0050_bb_cache/__tmp_forward_return_conditional.json"

            # 1) backup fixed input if exists
            if [ -f "${DST}" ]; then
              cp -f "${DST}" "${BAK_IN}"
            fi

            # 2) always copy src -> tmp, then tmp -> fixed (avoid same-file cp)
            cp -f "${SRC}" "${TMP_IN}"
            mv -f "${TMP_IN}" "${DST}"

            # 3) run old renderer
            python scripts/render_tw0050_forward_return_conditional_report.py

            # 4) move fixed output to target name
            if [ -f "${FIXED_OUT}" ]; then
              mv -f "${FIXED_OUT}" "tw0050_bb_cache/${OUT_MD}"
            else
              echo "ERROR: render v1 did not produce expected fixed output: ${FIXED_OUT}"
              exit 1
            fi

            # 5) restore fixed input if backup exists
            if [ -f "${BAK_IN}" ]; then
              mv -f "${BAK_IN}" "${DST}"
            fi
          }

          render_one forward_return_conditional.json forward_return_conditional_report.md
          render_one forward_return_conditional_5y.json forward_return_conditional_5y_report.md
          render_one forward_return_conditional_3y.json forward_return_conditional_3y_report.md

          echo "=== rendered reports ==="
          ls -al tw0050_bb_cache/*report*.md || true

      - name: Commit artifacts (if changed)
        shell: bash
        run: |
          set -e
          if [ -n "$(git status --porcelain)" ]; then
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git add \
              tw0050_bb_cache/forward_return_conditional.json \
              tw0050_bb_cache/forward_return_conditional_5y.json \
              tw0050_bb_cache/forward_return_conditional_3y.json \
              tw0050_bb_cache/forward_return_conditional_report.md \
              tw0050_bb_cache/forward_return_conditional_5y_report.md \
              tw0050_bb_cache/forward_return_conditional_3y_report.md
            git commit -m "Update forward_return_conditional (all/5y/3y) + reports"
            git push
          else
            echo "No changes to commit."
          fi