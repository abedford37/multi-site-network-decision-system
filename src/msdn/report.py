"""Render the pipeline as one figure and print a run summary."""
from __future__ import annotations

import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

PALETTE = ["#0055FF", "#E2AD28", "#4CAE4F", "#E92063", "#7A5CFF"]
INK, MUTED, BG = "#1A1A1A", "#666666", "#FAFAFC"


def build_pipeline_figure(state, path):
    s = state.summary()
    b = s["buckets"]
    stages = [
        ("1  Demand forecasting", "classify pattern, forecast rate",
         [f"{s['items']} items classified",
          f"smooth {b.get('smooth',0)} / intermittent {b.get('intermittent',0)}",
          f"lumpy {b.get('lumpy',0)} / new {b.get('new',0)}"]),
        ("2  Inventory policy", "MIN / OPHQ / MAX per item",
         [f"A {s['abc'].get('A',0)}  B {s['abc'].get('B',0)}  C {s['abc'].get('C',0)}",
          "service by class",
          "variability safety stock"]),
        ("3  Home assignment", "slot to buildings, park the tail",
         [f"{s['forward_homed']} forward, {s['storage_homed']} storage",
          f"new {s['placement'].get('new',0)} provisional",
          f"dead {s['placement'].get('dead',0)} + slow {s['placement'].get('slow',0)} parked"]),
        ("4  Container routing", "route inbound to building, day",
         [f"{s['containers_scheduled']} scheduled, {s['containers_deferred']} deferred",
          f"coverage {s['container_coverage']:.0%}",
          "feeds ETAs downstream"]),
        ("5  Transfer + reverse replen", "the day's moves under capacity",
         [f"{s['transfers_used']} transfers",
          f"outbound shortfall closed {s['outbound_shortfall_closed']:.0%}",
          f"{s['suppressed_by_inbound']:.0f} units suppressed by ETAs"]),
    ]

    fig, ax = plt.subplots(figsize=(15, 4.3))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    n = len(stages)
    w, gap = 2.5, 0.55
    for i, (title, sub, lines) in enumerate(stages):
        x = i * (w + gap)
        color = PALETTE[i]
        ax.add_patch(FancyBboxPatch((x, 1.35), w, 2.45, boxstyle="round,pad=0.05,rounding_size=0.12",
                                    fc="white", ec=color, lw=2, zorder=2))
        ax.add_patch(FancyBboxPatch((x, 3.15), w, 0.65, boxstyle="round,pad=0.05,rounding_size=0.12",
                                    fc=color, ec=color, lw=2, zorder=3))
        ax.text(x + w / 2, 3.46, title, ha="center", va="center", color="white",
                fontsize=10.5, weight="bold", zorder=4)
        ax.text(x + w / 2, 2.92, sub, ha="center", va="center", color=MUTED, fontsize=8.7,
                style="italic", zorder=4)
        for j, ln in enumerate(lines):
            ax.text(x + w / 2, 2.5 - j * 0.42, ln, ha="center", va="center", color=INK,
                    fontsize=9, zorder=4)
        if i < n - 1:
            ax.annotate("", xy=(x + w + gap, 2.1), xytext=(x + w, 2.1),
                        arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.8), zorder=1)

    ax.text(0, 4.35, "MSDN pipeline: one catalog, five decisions",
            fontsize=15, weight="bold", color=INK)
    ax.text(0, 4.02, "Each stage consumes the previous stage's output. Shared item ids and one "
                     "FWD-A / FWD-B / STORAGE network throughout.", fontsize=9.5, color=MUTED)
    ax.set_xlim(-0.2, n * (w + gap)); ax.set_ylim(1.0, 4.7)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(path, dpi=130, facecolor=BG); plt.close()


def print_summary(state):
    s = state.summary()
    print("MSDN pipeline run")
    print(f"  demand    : {s['items']} items, buckets {s['buckets']}")
    print(f"  policy    : ABC {s['abc']}")
    print(f"  home      : {s['forward_homed']} forward, {s['storage_homed']} storage "
          f"(placement {s['placement']})")
    print(f"  container : {s['containers_scheduled']} scheduled, {s['containers_deferred']} deferred, "
          f"coverage {s['container_coverage']:.0%}")
    print(f"  transfer  : {s['transfers_used']} moves, shortfall closed "
          f"{s['outbound_shortfall_closed']:.0%}, {s['suppressed_by_inbound']:.0f} units suppressed")
