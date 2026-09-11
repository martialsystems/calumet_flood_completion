# Copyright (c) 2026 Martial Systems LLC
"""Two README figures from locked Stage C/D JSON. No rasters. Not a FIRM."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from calumetmap.claims import require_clean
from calumetmap.config import INDY_PLANT_NAMES, P_DEFINITION
from calumetmap.errors import GateError

SCREEN_P = 0.50
FIG1_NAME = "pr_auc.png"
FIG2_NAME = "p_max_screen.png"

_SHORT = (
    ("HAMMOND GROUP", "Hammond Group"),
    ("RESCO PRODUCTS", "Resco"),
    ("REWORLD OIL", "Reworld Oil"),
    ("BEFESA ZINC", "Befesa Zinc"),
    ("USS GARY", "USS Gary"),
)


def short_name(name: str) -> str:
    raw = str(name or "").strip()
    upper = raw.upper()
    for plant in INDY_PLANT_NAMES:
        if plant.lower() in raw.lower():
            raise GateError("figure refuses an Indy plant name")
    for needle, short in _SHORT:
        if needle in upper:
            return short
    return raw.split("-")[0].strip()[:22]


def _f3(value: float) -> str:
    return f"{float(value):.3f}"


def pr_auc_title(*, c: float, hand: float, prevalence: float) -> str:
    title = (
        f"Stage C PR-AUC {_f3(c)} beats HAND {_f3(hand)} "
        f"(prevalence {_f3(prevalence)}). Modest. Not a FIRM."
    )
    require_clean(title, source="fig1_title")
    return title


def pmax_title() -> str:
    title = (
        f"Five Zone X sites: window p_max vs p_mean. Nobody clears {SCREEN_P:.2f}."
    )
    require_clean(title, source="fig2_title")
    return title


def write_pr_auc(
    dest: Path,
    *,
    pr_auc: float,
    hand_pr_auc: float,
    prevalence: float,
) -> Path:
    title = pr_auc_title(c=pr_auc, hand=hand_pr_auc, prevalence=prevalence)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = ["Stage C", "HAND", "prevalence"]
    vals = [float(pr_auc), float(hand_pr_auc), float(prevalence)]
    colors = ["#1b9e77", "#7570b3", "#d9d9d9"]
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    bars = ax.bar(labels, vals, color=colors, width=0.62)
    ax.set_ylabel("PR-AUC")
    ax.set_ylim(0.0, max(0.40, max(vals) + 0.06))
    ax.set_title(title, fontsize=9)
    for bar, v in zip(bars, vals, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            v + 0.008,
            _f3(v),
            ha="center",
            va="bottom",
            fontsize=9,
        )
    footer = (
        f"{P_DEFINITION} is map-completion, not a 1-percent annual-chance product."
    )
    require_clean(footer, source="fig1_footer")
    ax.text(0.5, -0.18, footer, transform=ax.transAxes, ha="center", fontsize=8)
    fig.subplots_adjust(bottom=0.22, top=0.86)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=120)
    plt.close(fig)
    return dest


def write_pmax_screen(dest: Path, *, rows: list[Mapping[str, Any]]) -> Path:
    if len(rows) != 5:
        raise GateError("fig2 needs five headline rows")
    pmax = [float(r["p_max"]) for r in rows]
    if any(v >= SCREEN_P for v in pmax):
        raise GateError("headline p_max cleared 0.50; figure is the below-line screen")
    title = pmax_title()
    names = [short_name(str(r["name"])) for r in rows]
    pmean = [float(r["p_mean"]) for r in rows]
    if names and names[0] == "USS Gary":
        raise GateError("USS Gary is not the p_max headline")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    x = np.arange(len(names), dtype=float)
    width = 0.36
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    bars_max = ax.bar(x - width / 2.0, pmax, width, label="p_max", color="#d95f02")
    ax.bar(x + width / 2.0, pmean, width, label="p_mean", color="#1b9e77")
    ax.axhline(SCREEN_P, color="#333333", linestyle="--", linewidth=1.2, label="0.50")
    for bar, v in zip(bars_max, pmax, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            v + 0.012,
            _f3(v),
            ha="center",
            va="bottom",
            fontsize=8,
        )
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("calibrated P")
    ax.set_ylim(0.0, 0.62)
    ax.set_title(title, fontsize=9)
    ax.legend(loc="upper right", fontsize=8, framealpha=0.92)
    footer = "Rank is p_max. Inventory pounds are not the lead."
    require_clean(footer, source="fig2_footer")
    fig.text(0.5, 0.03, footer, ha="center", fontsize=8)
    fig.subplots_adjust(bottom=0.18, top=0.86)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=120)
    plt.close(fig)
    return dest


def restamp_readme_figures(
    dest_dir: Path,
    *,
    stage_c_path: Path,
    stage_d_path: Path,
) -> list[Path]:
    c = json.loads(stage_c_path.read_text(encoding="utf-8"))
    d = json.loads(stage_d_path.read_text(encoding="utf-8"))
    rows = list(d.get("d1_headline_rows") or [])
    if len(rows) != 5:
        raise GateError("stage D JSON missing five headline rows")
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        write_pr_auc(
            dest_dir / FIG1_NAME,
            pr_auc=float(c["pr_auc"]),
            hand_pr_auc=float(c["hand_negated_pr_auc"]),
            prevalence=float(c["pr_auc_baseline"]),
        ),
        write_pmax_screen(dest_dir / FIG2_NAME, rows=rows),
    ]
    return paths
