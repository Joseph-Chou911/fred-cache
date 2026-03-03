#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
make_episode_charts.py

Snapshot charts for a single episode pack (video_pack/episode_pack.json).

Reads:
- episode_pack.json (output of build_video_pack.py)

Writes PNG charts to --out_dir.

Key design:
- Audit-first: ONLY uses values available in the pack (raw or extracts).
- Headroom fix: bar labels will NOT collide with the title (adds ylim headroom + title pad).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

import matplotlib
matplotlib.use("Agg", force=True)  # headless
import matplotlib.pyplot as plt


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def deep_get(obj: Any, path: str) -> Any:
    cur = obj
    for token in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(token)
        elif isinstance(cur, list):
            if token.isdigit():
                idx = int(token)
                if 0 <= idx < len(cur):
                    cur = cur[idx]
                else:
                    return None
            else:
                return None
        else:
            return None
    return cur


def _as_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _as_str(x: Any) -> str:
    return "N/A" if x is None else str(x)


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def add_headroom_for_barlabels(ax, bars, headroom_ratio: float = 0.08) -> None:
    """
    Prevent collision of bar labels with the title by increasing y max.
    """
    heights = [b.get_height() for b in bars if b is not None]
    if not heights:
        return

    ymin, ymax = ax.get_ylim()
    top = max(heights)

    # If the chart is percent-like (0-100), we explicitly cap at 110 for clean look.
    if 0 <= top <= 100 and 0 <= ymax <= 100.0001:
        ax.set_ylim(0, 110)
        return

    # Generic case: increase y-limit
    new_ymax = max(ymax, top) * (1.0 + headroom_ratio)
    ax.set_ylim(ymin, new_ymax)


def save_fig(fig, out_path: Path) -> None:
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_roll25_percentiles(pack: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    r = deep_get(pack, "raw.roll25") or {}
    asof = (
        deep_get(pack, "inputs.roll25.as_of_date")
        or deep_get(r, "used_date")
        or deep_get(r, "series.trade_value.asof")
        or deep_get(r, "series.close.asof")
    )

    items: List[Tuple[str, Optional[float]]] = [
        ("trade_value p60", _as_float(deep_get(r, "series.trade_value.win60.p"))),
        ("trade_value p252", _as_float(deep_get(r, "series.trade_value.win252.p"))),
        ("close p252", _as_float(deep_get(r, "series.close.win252.p"))),
        ("amplitude p60", _as_float(deep_get(r, "series.amplitude_pct.win60.p"))),
        ("amplitude p252", _as_float(deep_get(r, "series.amplitude_pct.win252.p"))),
    ]
    labels = [k for k, v in items if v is not None]
    values = [v for _, v in items if v is not None]

    if not values:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(labels, values)
    ax.set_ylabel("Percentile (0-100)")
    ax.set_title(f"roll25 percentiles (as_of={_as_str(asof)})", pad=16)

    # Bar labels
    ax.bar_label(bars, fmt="%.1f", padding=3)
    add_headroom_for_barlabels(ax, bars, headroom_ratio=0.10)

    fig.tight_layout(rect=(0, 0, 1, 0.98))
    out_path = out_dir / "01_roll25_percentiles.png"
    save_fig(fig, out_path)
    return out_path


def plot_roll25_zscores(pack: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    r = deep_get(pack, "raw.roll25") or {}
    asof = (
        deep_get(pack, "inputs.roll25.as_of_date")
        or deep_get(r, "used_date")
        or deep_get(r, "series.trade_value.asof")
        or deep_get(r, "series.close.asof")
    )

    items: List[Tuple[str, Optional[float]]] = [
        ("trade_value z60", _as_float(deep_get(r, "series.trade_value.win60.z"))),
        ("trade_value z252", _as_float(deep_get(r, "series.trade_value.win252.z"))),
        ("close z252", _as_float(deep_get(r, "series.close.win252.z"))),
        ("amplitude z60", _as_float(deep_get(r, "series.amplitude_pct.win60.z"))),
        ("amplitude z252", _as_float(deep_get(r, "series.amplitude_pct.win252.z"))),
    ]
    labels = [k for k, v in items if v is not None]
    values = [v for _, v in items if v is not None]
    if not values:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(labels, values)
    ax.set_ylabel("Z-score")
    ax.set_title(f"roll25 z-scores (as_of={_as_str(asof)})", pad=16)

    ax.bar_label(bars, fmt="%.2f", padding=3)
    add_headroom_for_barlabels(ax, bars, headroom_ratio=0.15)

    fig.tight_layout(rect=(0, 0, 1, 0.98))
    out_path = out_dir / "02_roll25_zscores.png"
    save_fig(fig, out_path)
    return out_path


def plot_margin_snapshot(pack: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    m = deep_get(pack, "raw.taiwan_margin") or {}
    asof = deep_get(pack, "inputs.taiwan_margin.as_of_date") or deep_get(m, "series.TWSE.data_date")

    twse_bal = _as_float(deep_get(m, "series.TWSE.rows.0.balance_yi"))
    tpex_bal = _as_float(deep_get(m, "series.TPEX.rows.0.balance_yi"))
    twse_chg = _as_float(deep_get(m, "series.TWSE.rows.0.chg_yi"))
    tpex_chg = _as_float(deep_get(m, "series.TPEX.rows.0.chg_yi"))

    if twse_bal is None and tpex_bal is None:
        return None

    # balances
    labels = ["TWSE", "TPEX", "TOTAL"]
    vals = [
        twse_bal if twse_bal is not None else 0.0,
        tpex_bal if tpex_bal is not None else 0.0,
        (twse_bal or 0.0) + (tpex_bal or 0.0),
    ]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(labels, vals)
    ax.set_ylabel("Balance (億)")
    ax.set_title(f"Margin balances (as_of={_as_str(asof)})", pad=16)
    ax.bar_label(bars, fmt="%.1f", padding=3)
    add_headroom_for_barlabels(ax, bars, headroom_ratio=0.08)

    # annotate daily changes under title area (figure text to avoid overlay on bars)
    notes = []
    if twse_chg is not None:
        notes.append(f"TWSE Δ={twse_chg:+.1f}億")
    if tpex_chg is not None:
        notes.append(f"TPEX Δ={tpex_chg:+.1f}億")
    if twse_chg is not None and tpex_chg is not None:
        notes.append(f"TOTAL Δ={(twse_chg + tpex_chg):+.1f}億")
    if notes:
        fig.text(0.5, 0.02, " / ".join(notes), ha="center", va="bottom")

    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    out_path = out_dir / "03_margin_balances.png"
    save_fig(fig, out_path)
    return out_path


def plot_tw0050_bb_position(pack: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    tw = deep_get(pack, "raw.tw0050_bb") or {}
    asof = deep_get(pack, "inputs.tw0050_bb.as_of_date") or deep_get(tw, "meta.last_date") or deep_get(tw, "latest.date")

    price = _as_float(deep_get(tw, "latest.adjclose")) or _as_float(deep_get(tw, "latest.price_used"))
    bb_ma = _as_float(deep_get(tw, "latest.bb_ma"))
    bb_up = _as_float(deep_get(tw, "latest.bb_upper"))
    bb_lo = _as_float(deep_get(tw, "latest.bb_lower"))
    bb_z = _as_float(deep_get(tw, "latest.bb_z"))
    state = deep_get(tw, "latest.state")

    if price is None or bb_ma is None or bb_up is None or bb_lo is None:
        return None

    labels = ["BB lower", "BB MA", "Price", "BB upper"]
    vals = [bb_lo, bb_ma, price, bb_up]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(range(len(vals)), vals, marker="o")
    ax.set_xticks(range(len(labels)), labels)
    ax.set_ylabel("Price")
    ax.set_title(f"0050 BB position (as_of={_as_str(asof)})", pad=16)

    # simple value labels near points
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom")

    # bottom note (keeps the plot clean)
    note_parts = []
    if state is not None:
        note_parts.append(f"state={state}")
    if bb_z is not None:
        note_parts.append(f"bb_z={bb_z:.3f}")
    rv_pctl = _as_float(deep_get(tw, "vol.rv_ann_pctl"))
    if rv_pctl is not None:
        note_parts.append(f"rv_pctl={rv_pctl:.1f}")
    if note_parts:
        fig.text(0.5, 0.02, " / ".join(note_parts), ha="center", va="bottom")

    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    out_path = out_dir / "04_tw0050_bb_position.png"
    save_fig(fig, out_path)
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode_pack", required=True, help="Path to episode_pack.json")
    ap.add_argument("--out_dir", required=True, help="Output directory for charts")
    args = ap.parse_args()

    pack = load_json(args.episode_pack)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

    # Generate charts (best-effort; no crash if some fields missing)
    plot_roll25_percentiles(pack, out_dir)
    plot_roll25_zscores(pack, out_dir)
    plot_margin_snapshot(pack, out_dir)
    plot_tw0050_bb_position(pack, out_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())