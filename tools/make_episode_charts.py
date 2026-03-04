#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
make_episode_charts.py

Snapshot charts for ONE episode using episode_pack.json (built by build_video_pack.py).

Design goal:
- "Today snapshot" only (no long history lines).
- Output PNGs + chart_manifest.json (audit-first).
- Keep text readable for YouTube overlays.

Inputs:
- --episode_pack: path to episode_pack.json

Outputs (to --out_dir):
- 00_episode_snapshot.png                (text-based one-page snapshot)
- 01_roll25_percentile_bars.png          (p(0-100) bars: trade_value/close/amplitude)
- 02_margin_balance_bars.png             (TWSE/TPEX/TOTAL balances)
- 03_margin_change_bars.png              (TWSE/TPEX/TOTAL daily chg)
- 04_0050_bb_band_gauge.png              (BB lower/ma/upper with price marker)
- [optional] 05_0050_tranche_levels.png  (price levels from tranche_levels; default OFF)
- episode_chart_ready.csv                (flat table for downstream)
- chart_manifest.json                    (what charts were produced, with sha256, as_of, warnings)

Dependencies:
- matplotlib, numpy, pandas (pandas optional but recommended; used for CSV convenience)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt  # noqa: E402


TZ_NAME_DEFAULT = "Asia/Taipei"
MANIFEST_SCHEMA = "chart_manifest_v1"
SCRIPT_FINGERPRINT = "make_episode_charts@v1.4.bb_gauge_arrow_labels"


# -----------------------------
# Helpers (audit-first)
# -----------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)


def fmt_float(x: Any, nd: int = 2, na: str = "N/A") -> str:
    try:
        if x is None:
            return na
        return f"{float(x):.{nd}f}"
    except Exception:
        return na


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


def extracts_to_map(ext_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {e.get("field"): e.get("value") for e in (ext_list or [])}


def save_fig(fig: plt.Figure, out_path: Path, dpi: int) -> Dict[str, Any]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    b = out_path.read_bytes()
    w_in, h_in = fig.get_size_inches()
    return {
        "file": out_path.name,
        "path": str(out_path),
        "sha256": sha256_bytes(b),
        "dpi": dpi,
        "size_inches": [float(w_in), float(h_in)],
    }


def set_font_defaults() -> None:
    plt.rcParams["font.sans-serif"] = [
        "Noto Sans CJK TC",
        "Noto Sans CJK SC",
        "Noto Sans CJK JP",
        "Microsoft JhengHei",
        "PingFang TC",
        "Heiti TC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def _set_ylim_with_headroom(ax: plt.Axes, values: List[float], *, pct_like: bool = False, ratio: float = 0.10) -> None:
    if not values:
        return
    ymin, ymax = ax.get_ylim()
    vmin = min(values)
    vmax = max(values)

    if pct_like:
        ax.set_ylim(0, 110)
        return

    base_top = max(ymax, vmax)
    if base_top == 0:
        ax.set_ylim(ymin, 1)
    else:
        ax.set_ylim(min(ymin, vmin), base_top * (1.0 + ratio))


def _bar_label_safe(ax: plt.Axes, bars, *, fmt: str, fontsize: int = 9, padding: int = 3) -> None:
    if hasattr(ax, "bar_label"):
        ax.bar_label(bars, fmt=fmt, padding=padding, fontsize=fontsize)
        return
    try:
        for b in bars:
            h = float(b.get_height())
            x = b.get_x() + b.get_width() / 2
            ax.text(x, h, fmt % h, ha="center", va="bottom", fontsize=fontsize)
    except Exception:
        return


def _annotate_near_point(
    ax: plt.Axes,
    *,
    x: float,
    y: float,
    text: str,
    dx: float,
    dy: float,
    ha: str,
    va: str,
    fontsize: int = 9,
    arrow: bool = False,
    arrow_color: Optional[str] = None,
    arrow_lw: float = 1.0,
) -> None:
    """
    Place a label close to (x,y) using offset points so it "sticks" to the marker.
    If arrow=True, draw an arrow from label to the exact point.
    """
    arrowprops = None
    if arrow:
        arrowprops = {
            "arrowstyle": "->",
            "lw": arrow_lw,
            "color": arrow_color if arrow_color is not None else "0.35",
            "shrinkA": 0,
            "shrinkB": 0,
            "connectionstyle": "arc3,rad=0.0",
        }

    ax.annotate(
        text,
        xy=(x, y),
        xytext=(dx, dy),
        textcoords="offset points",
        ha=ha,
        va=va,
        fontsize=fontsize,
        arrowprops=arrowprops,
        clip_on=False,
    )


# -----------------------------
# Chart builders (snapshot)
# -----------------------------
def chart_00_episode_snapshot(pack: Dict[str, Any], out_dir: Path, dpi: int) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    tz = pack.get("timezone") or TZ_NAME_DEFAULT
    day = pack.get("day_key_local") or "N/A"
    pack_warnings = pack.get("warnings") or []
    if not isinstance(pack_warnings, list):
        pack_warnings = ["pack_warnings_not_list"]
    warnings.extend([str(x) for x in pack_warnings])

    inp = pack.get("inputs") or {}
    ext = pack.get("extracts_best_effort") or {}
    r = extracts_to_map(ext.get("roll25", []))
    m = extracts_to_map(ext.get("margin", []))
    t = extracts_to_map(ext.get("tw0050_bb", []))

    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    header = f"Episode Snapshot | day={day} ({tz})"
    sub = f"pack.generated_at_local={pack.get('generated_at_local','N/A')} | build={pack.get('build_fingerprint','N/A')}"
    ax.text(0.02, 0.95, header, fontsize=16, fontweight="bold", va="top")
    ax.text(0.02, 0.91, sub, fontsize=9, va="top")

    def _inp_line(k: str) -> str:
        v = inp.get(k, {}) if isinstance(inp, dict) else {}
        return f"{k}: as_of={v.get('as_of_date','N/A')} age_days={v.get('age_days','N/A')} fp={v.get('fingerprint','N/A')}"

    ax.text(0.02, 0.86, "Inputs:", fontsize=10, fontweight="bold", va="top")
    ax.text(0.02, 0.83, _inp_line("roll25"), fontsize=9, va="top")
    ax.text(0.02, 0.80, _inp_line("taiwan_margin"), fontsize=9, va="top")
    ax.text(0.02, 0.77, _inp_line("tw0050_bb"), fontsize=9, va="top")

    warn_txt = "NONE" if not warnings else ", ".join(warnings)
    ax.text(0.02, 0.72, f"Warnings: {warn_txt}", fontsize=9, va="top")

    y = 0.66
    ax.text(0.02, y, "roll25 (TWSE Turnover / Heat):", fontsize=11, fontweight="bold", va="top")
    y -= 0.04
    roll_lines = [
        f"used_date={r.get('used_date','N/A')} mode={r.get('mode','N/A')}",
        f"trade_value win60: z={fmt_float(r.get('trade_value_win60_z'),3)} p={fmt_float(r.get('trade_value_win60_p'),3)} value={fmt_float(r.get('trade_value_win60_value'),0)}",
        f"trade_value win252: z={fmt_float(r.get('trade_value_win252_z'),3)} p={fmt_float(r.get('trade_value_win252_p'),3)} value={fmt_float(r.get('trade_value_win252_value'),0)}",
        f"close win252: z={fmt_float(r.get('close_win252_z'),3)} p={fmt_float(r.get('close_win252_p'),3)}",
        f"vol_multiplier_20={fmt_float(r.get('vol_multiplier_20'),3)} | volume_amplified={r.get('volume_amplified','N/A')} | consecutive_down_days={r.get('consecutive_down_days','N/A')}",
    ]
    for s in roll_lines:
        ax.text(0.04, y, s, fontsize=9, va="top")
        y -= 0.03

    y -= 0.01
    ax.text(0.02, y, "taiwan_margin (Leverage):", fontsize=11, fontweight="bold", va="top")
    y -= 0.04
    margin_lines = [
        f"date={m.get('twse_data_date','N/A')}",
        f"TWSE balance(億)={fmt_float(m.get('twse_balance_yi'),1)} chg(億)={fmt_float(m.get('twse_chg_yi'),1)}",
        f"TPEX balance(億)={fmt_float(m.get('tpex_balance_yi'),1)} chg(億)={fmt_float(m.get('tpex_chg_yi'),1)}",
        f"TOTAL balance(億)={fmt_float(m.get('total_balance_yi'),1)} chg(億)={fmt_float(m.get('total_chg_yi'),1)}",
        f"3rows chg sum: TWSE={fmt_float(m.get('twse_chg_sum_3rows'),1)} TPEX={fmt_float(m.get('tpex_chg_sum_3rows'),1)} TOTAL={fmt_float(m.get('total_chg_sum_3rows'),1)}",
        f"30rows high balance: TWSE={m.get('twse_is_30rows_high_balance','N/A')} TPEX={m.get('tpex_is_30rows_high_balance','N/A')}",
    ]
    for s in margin_lines:
        ax.text(0.04, y, s, fontsize=9, va="top")
        y -= 0.03

    y -= 0.01
    ax.text(0.02, y, "tw0050_bb (0050 Position):", fontsize=11, fontweight="bold", va="top")
    y -= 0.04
    veto_reasons = t.get("pledge_veto_reasons")
    if isinstance(veto_reasons, list):
        veto_str = "; ".join([str(x) for x in veto_reasons][:4])
    else:
        veto_str = str(veto_reasons) if veto_reasons is not None else "N/A"

    t_lines = [
        f"last_date={t.get('last_date','N/A')} price={fmt_float(t.get('adjclose'),2)} state={t.get('bb_state','N/A')} bb_z={fmt_float(t.get('bb_z'),3)}",
        f"BB: lower={fmt_float(t.get('bb_lower'),2)} ma={fmt_float(t.get('bb_ma'),2)} upper={fmt_float(t.get('bb_upper'),2)}",
        f"dist_to_upper_pct={fmt_float(t.get('dist_to_upper_pct'),3)} | dist_to_lower_pct={fmt_float(t.get('dist_to_lower_pct'),3)}",
        f"trend_state={t.get('trend_state','N/A')} | price_vs_200ma_pct={fmt_float(t.get('price_vs_200ma_pct'),2)} | slope_pct={fmt_float(t.get('trend_slope_pct'),2)}",
        f"rv_ann={fmt_float(t.get('rv_ann'),3)} | rv_ann_pctl={fmt_float(t.get('rv_ann_pctl'),2)}",
        f"regime_allowed={t.get('regime_allowed','N/A')} | pledge_action_bucket={t.get('pledge_action_bucket','N/A')}",
        f"pledge_veto_reasons={veto_str}",
    ]
    for s in t_lines:
        ax.text(0.04, y, s, fontsize=9, va="top")
        y -= 0.03

    ax.text(
        0.02,
        0.02,
        "Note: Snapshot for reporting/logging; not investment advice. Use manifest for audit.",
        fontsize=8,
        va="bottom",
    )

    meta = save_fig(fig, out_dir / "00_episode_snapshot.png", dpi=dpi)
    meta["title"] = "Episode snapshot (one-page text)"
    return meta, warnings


def chart_01_roll25_percentile_bars(pack: Dict[str, Any], out_dir: Path, dpi: int) -> Optional[Dict[str, Any]]:
    raw_r25 = deep_get(pack, "raw.roll25") or {}
    items: List[Tuple[str, Optional[float]]] = [
        ("trade_value p60", deep_get(raw_r25, "series.trade_value.win60.p")),
        ("trade_value p252", deep_get(raw_r25, "series.trade_value.win252.p")),
        ("close p252", deep_get(raw_r25, "series.close.win252.p")),
        ("amplitude p60", deep_get(raw_r25, "series.amplitude_pct.win60.p")),
        ("amplitude p252", deep_get(raw_r25, "series.amplitude_pct.win252.p")),
    ]

    labels: List[str] = []
    values: List[float] = []
    for k, v in items:
        if isinstance(v, (int, float)):
            labels.append(k)
            values.append(float(v))

    if not values:
        return None

    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)

    bars = ax.bar(labels, values)

    ax.set_ylabel("Percentile (0-100)")
    _set_ylim_with_headroom(ax, values, pct_like=True)

    asof = deep_get(raw_r25, "used_date") or deep_get(raw_r25, "series.trade_value.asof") or "N/A"
    ax.set_title(f"roll25 percentiles (as_of={asof})", pad=16)

    _bar_label_safe(ax, bars, fmt="%.1f", fontsize=9, padding=3)

    fig.autofmt_xdate(rotation=0)
    fig.tight_layout(rect=(0, 0, 1, 0.98))

    meta = save_fig(fig, out_dir / "01_roll25_percentile_bars.png", dpi=dpi)
    meta["title"] = "roll25 percentiles bars"
    return meta


def chart_02_03_margin_bars(pack: Dict[str, Any], out_dir: Path, dpi: int) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    ext = pack.get("extracts_best_effort") or {}
    m = extracts_to_map(ext.get("margin", []))

    twse_bal = m.get("twse_balance_yi")
    tpex_bal = m.get("tpex_balance_yi")
    total_bal = m.get("total_balance_yi")

    twse_chg = m.get("twse_chg_yi")
    tpex_chg = m.get("tpex_chg_yi")
    total_chg = m.get("total_chg_yi")

    meta_bal = None
    vals_bal: List[Tuple[str, float]] = []
    for k, v in [("TWSE", twse_bal), ("TPEX", tpex_bal), ("TOTAL", total_bal)]:
        if isinstance(v, (int, float)):
            vals_bal.append((k, float(v)))

    if vals_bal:
        fig = plt.figure(figsize=(8, 4.5))
        ax = fig.add_subplot(111)
        labels = [x[0] for x in vals_bal]
        values = [x[1] for x in vals_bal]
        bars = ax.bar(labels, values)
        ax.set_ylabel("Balance (億)")
        asof = m.get("twse_data_date") or m.get("tpex_data_date") or "N/A"
        ax.set_title(f"Margin balance (as_of={asof})", pad=16)

        _set_ylim_with_headroom(ax, values, pct_like=False, ratio=0.08)
        _bar_label_safe(ax, bars, fmt="%.1f", fontsize=9, padding=3)

        fig.tight_layout(rect=(0, 0, 1, 0.98))
        meta_bal = save_fig(fig, out_dir / "02_margin_balance_bars.png", dpi=dpi)
        meta_bal["title"] = "Margin balance bars"

    meta_chg = None
    vals_chg: List[Tuple[str, float]] = []
    for k, v in [("TWSE", twse_chg), ("TPEX", tpex_chg), ("TOTAL", total_chg)]:
        if isinstance(v, (int, float)):
            vals_chg.append((k, float(v)))

    if vals_chg:
        fig = plt.figure(figsize=(8, 4.5))
        ax = fig.add_subplot(111)
        labels = [x[0] for x in vals_chg]
        values = [x[1] for x in vals_chg]
        bars = ax.bar(labels, values)
        ax.axhline(0.0)
        ax.set_ylabel("Daily change (億)")
        asof = m.get("twse_data_date") or m.get("tpex_data_date") or "N/A"
        ax.set_title(f"Margin daily change (as_of={asof})", pad=16)

        ymin = min(values)
        ymax = max(values)
        span = max(ymax - ymin, 1e-6)
        ax.set_ylim(ymin - 0.12 * span, ymax + 0.12 * span)

        if hasattr(ax, "bar_label"):
            ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=9)
        else:
            for b in bars:
                h = float(b.get_height())
                x = b.get_x() + b.get_width() / 2
                ax.text(x, h, f"{h:.1f}", ha="center", va="bottom" if h >= 0 else "top", fontsize=9)

        fig.tight_layout(rect=(0, 0, 1, 0.98))
        meta_chg = save_fig(fig, out_dir / "03_margin_change_bars.png", dpi=dpi)
        meta_chg["title"] = "Margin daily change bars"

    return meta_bal, meta_chg


def chart_04_0050_bb_band_gauge(pack: Dict[str, Any], out_dir: Path, dpi: int) -> Optional[Dict[str, Any]]:
    ext = pack.get("extracts_best_effort") or {}
    t = extracts_to_map(ext.get("tw0050_bb", []))

    price = t.get("adjclose")
    lower = t.get("bb_lower")
    ma = t.get("bb_ma")
    upper = t.get("bb_upper")

    if not all(isinstance(x, (int, float)) for x in [price, lower, ma, upper]):
        return None

    price = float(price)
    lower = float(lower)
    ma = float(ma)
    upper = float(upper)

    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)

    # explicit colors (upper/lower dots != price dot)
    band_color = "C0"
    price_color = "C1"
    bound_color = "C2"

    y0 = 0.0

    ax.hlines(y0, lower, upper, linewidth=2.0, color=band_color)
    ax.scatter([lower, upper], [y0, y0], s=90, marker="o", color=bound_color, zorder=3)
    ax.scatter([ma], [y0], marker="|", s=1100, color=band_color, zorder=4)
    ax.scatter([price], [y0], s=120, marker="o", color=price_color, zorder=5)

    ax.set_yticks([])
    ax.set_xlabel("Price")
    ax.set_title(
        f"0050 BB band position (as_of={t.get('last_date','N/A')}) | state={t.get('bb_state','N/A')} | z={fmt_float(t.get('bb_z'),3)}",
        pad=16,
    )

    span = max(upper - lower, 1e-6)
    ax.set_xlim(lower - 0.10 * span, upper + 0.10 * span)
    ax.set_ylim(-1.0, 1.0)

    # -----------------------------
    # Label collision avoidance + arrows to point markers
    # -----------------------------
    near_thr = 0.12
    very_near_thr = 0.06
    d_upper = abs(price - upper) / span
    d_lower = abs(price - lower) / span

    lower_cfg = dict(dx=4, dy=14, ha="left", va="bottom")
    upper_cfg = dict(dx=-4, dy=14, ha="right", va="bottom")
    ma_cfg = dict(dx=0, dy=18, ha="center", va="bottom")
    price_cfg = dict(dx=0, dy=-18, ha="center", va="top")

    if d_upper < near_thr:
        upper_cfg["dy"] = 32 if d_upper >= very_near_thr else 42
        price_cfg["dx"] = -22
        price_cfg["dy"] = -22
        price_cfg["ha"] = "right"
    elif d_lower < near_thr:
        lower_cfg["dy"] = 32 if d_lower >= very_near_thr else 42
        price_cfg["dx"] = 22
        price_cfg["dy"] = -22
        price_cfg["ha"] = "left"

    # arrows (color-match each target marker to reduce ambiguity)
    _annotate_near_point(
        ax,
        x=lower,
        y=y0,
        text=f"lower={lower:.2f}",
        fontsize=9,
        arrow=True,
        arrow_color=bound_color,
        **lower_cfg,
    )
    _annotate_near_point(
        ax,
        x=upper,
        y=y0,
        text=f"upper={upper:.2f}",
        fontsize=9,
        arrow=True,
        arrow_color=bound_color,
        **upper_cfg,
    )
    _annotate_near_point(
        ax,
        x=ma,
        y=y0,
        text=f"ma={ma:.2f}",
        fontsize=9,
        arrow=True,
        arrow_color=band_color,
        **ma_cfg,
    )
    _annotate_near_point(
        ax,
        x=price,
        y=y0,
        text=f"price={price:.2f}",
        fontsize=9,
        arrow=True,
        arrow_color=price_color,
        **price_cfg,
    )

    fig.tight_layout(rect=(0, 0, 1, 0.98))
    meta = save_fig(fig, out_dir / "04_0050_bb_band_gauge.png", dpi=dpi)
    meta["title"] = "0050 BB band gauge (arrow labels to markers)"
    return meta


def chart_05_0050_tranche_levels(pack: Dict[str, Any], out_dir: Path, dpi: int) -> Optional[Dict[str, Any]]:
    ext = pack.get("extracts_best_effort") or {}
    t = extracts_to_map(ext.get("tw0050_bb", []))
    levels = t.get("tranche_levels")

    if not isinstance(levels, list) or not levels:
        return None

    rows: List[Tuple[str, float]] = []
    for item in levels:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "N/A"))
        pl = item.get("price_level")
        if isinstance(pl, (int, float)):
            rows.append((label, float(pl)))

    if not rows:
        return None

    rows.sort(key=lambda x: x[1], reverse=True)

    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    labels = [x[0] for x in rows]
    values = [x[1] for x in rows]
    bars = ax.bar(labels, values)
    ax.set_ylabel("Price level")
    ax.set_title(f"0050 tranche levels (as_of={t.get('last_date','N/A')})", pad=16)
    ax.text(
        0.01,
        0.98,
        "CAUTION: levels are statistical mapping, not buy/sell points.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
    )

    _set_ylim_with_headroom(ax, values, pct_like=False, ratio=0.08)
    _bar_label_safe(ax, bars, fmt="%.2f", fontsize=9, padding=3)

    fig.tight_layout(rect=(0, 0, 1, 0.98))

    meta = save_fig(fig, out_dir / "05_0050_tranche_levels.png", dpi=dpi)
    meta["title"] = "0050 tranche levels bars (anchoring caution)"
    return meta


def write_episode_chart_ready_csv(pack: Dict[str, Any], out_dir: Path) -> Path:
    out_path = out_dir / "episode_chart_ready.csv"
    out_dir.mkdir(parents=True, exist_ok=True)

    ext = pack.get("extracts_best_effort") or {}
    r = extracts_to_map(ext.get("roll25", []))
    m = extracts_to_map(ext.get("margin", []))
    t = extracts_to_map(ext.get("tw0050_bb", []))

    rows: List[Dict[str, Any]] = []
    for module, mp in [("roll25", r), ("margin", m), ("tw0050_bb", t)]:
        for k, v in mp.items():
            rows.append(
                {
                    "module": module,
                    "metric": k,
                    "value": json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v,
                }
            )

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["module", "metric", "value"])
        w.writeheader()
        w.writerows(rows)
    return out_path


def build_manifest(
    out_dir: Path,
    input_pack_path: Path,
    pack: Dict[str, Any],
    charts_meta: List[Dict[str, Any]],
    extra_warnings: List[str],
) -> Dict[str, Any]:
    tz = pack.get("timezone") or TZ_NAME_DEFAULT
    day = pack.get("day_key_local") or "N/A"

    ext = pack.get("extracts_best_effort") or {}
    r = extracts_to_map(ext.get("roll25", []))
    data_as_of = r.get("used_date")
    if not data_as_of:
        inp = pack.get("inputs") or {}
        candidates = []
        for k in ["roll25", "taiwan_margin", "tw0050_bb"]:
            v = inp.get(k, {}) if isinstance(inp, dict) else {}
            s = v.get("as_of_date")
            if isinstance(s, str) and s:
                candidates.append(s)
        data_as_of = max(candidates) if candidates else "N/A"

    warnings = []
    pack_warnings = pack.get("warnings") or []
    if isinstance(pack_warnings, list):
        warnings.extend([str(x) for x in pack_warnings])
    warnings.extend([str(x) for x in extra_warnings])

    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "script_fingerprint": SCRIPT_FINGERPRINT,
        "generated_at_utc": utc_now_iso(),
        "timezone": tz,
        "day_key_local": day,
        "data_as_of": data_as_of,
        "input_files": {
            "episode_pack": str(input_pack_path),
            "episode_pack_sha256": sha256_file(input_pack_path),
        },
        "pack_build_fingerprint": pack.get("build_fingerprint", "N/A"),
        "pack_generated_at_local": pack.get("generated_at_local", "N/A"),
        "warnings": sorted(list(dict.fromkeys(warnings))),
        "charts": charts_meta,
    }
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode_pack", required=True, help="Path to episode_pack.json")
    ap.add_argument("--out_dir", required=True, help="Output directory for PNGs + manifest")
    ap.add_argument("--dpi", default="160", help="PNG dpi (default 160 for 1280x720 at 8x4.5)")
    ap.add_argument(
        "--include_tranche_levels",
        action="store_true",
        help="Also output 05_0050_tranche_levels.png (may cause anchoring; default OFF).",
    )
    args = ap.parse_args()

    set_font_defaults()

    pack_path = Path(args.episode_pack)
    out_dir = Path(args.out_dir)
    dpi = int(args.dpi)

    out_dir.mkdir(parents=True, exist_ok=True)
    pack = load_json(pack_path)

    charts_meta: List[Dict[str, Any]] = []
    extra_warnings: List[str] = []

    meta0, w0 = chart_00_episode_snapshot(pack, out_dir, dpi)
    if meta0:
        charts_meta.append(meta0)
    extra_warnings.extend(w0)

    meta1 = chart_01_roll25_percentile_bars(pack, out_dir, dpi)
    if meta1:
        charts_meta.append(meta1)
    else:
        extra_warnings.append("roll25_percentile_bars_skipped_no_data")

    meta2, meta3 = chart_02_03_margin_bars(pack, out_dir, dpi)
    if meta2:
        charts_meta.append(meta2)
    else:
        extra_warnings.append("margin_balance_bars_skipped_no_data")
    if meta3:
        charts_meta.append(meta3)
    else:
        extra_warnings.append("margin_change_bars_skipped_no_data")

    meta4 = chart_04_0050_bb_band_gauge(pack, out_dir, dpi)
    if meta4:
        charts_meta.append(meta4)
    else:
        extra_warnings.append("tw0050_bb_gauge_skipped_no_data")

    if args.include_tranche_levels:
        meta5 = chart_05_0050_tranche_levels(pack, out_dir, dpi)
        if meta5:
            charts_meta.append(meta5)
        else:
            extra_warnings.append("tranche_levels_skipped_no_data")

    csv_path = write_episode_chart_ready_csv(pack, out_dir)
    charts_meta.append(
        {
            "file": csv_path.name,
            "path": str(csv_path),
            "sha256": sha256_file(csv_path),
            "title": "episode_chart_ready.csv (flat metrics table)",
        }
    )

    manifest = build_manifest(out_dir, pack_path, pack, charts_meta, extra_warnings)
    dump_json(out_dir / "chart_manifest.json", manifest)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())