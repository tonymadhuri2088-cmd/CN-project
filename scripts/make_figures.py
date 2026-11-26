"""Regenerate the README figures in docs/images/.

The values are the documented, log-verified numbers (see docs/research/claims.json and
claims_v2.json; `python -m netwing.reproduce check --strict` re-derives them from results/).
Run: python scripts/make_figures.py   (needs matplotlib)
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent.parent / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)
INK, MUTE, TEAL, AMBER, GREY, BG = "#14213D", "#6B7280", "#0E9F8E", "#E8A33D", "#B8C0CC", "#FFFFFF"
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": GREY,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "figure.facecolor": BG,
    }
)


def labels(ax, bars, fmt):
    for b in bars:
        ax.annotate(
            fmt(b.get_height()),
            (b.get_x() + b.get_width() / 2, b.get_height()),
            ha="center",
            va="bottom",
            fontsize=10,
            xytext=(0, 3),
            textcoords="offset points",
        )


def hard_suite():
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4.2))
    modes, col = ["plain", "healthy_ok", "netwing"], [GREY, GREY, TEAL]
    fa = [80, 90, 0]
    bars = a.bar(modes, fa, color=col)
    labels(a, bars, lambda v: f"{v:.0f}%")
    a.set_ylim(0, 105)
    a.set_ylabel("false alarms on healthy networks (%)")
    a.set_title("False alarms (hard suite)", loc="left", fontweight="bold")
    a.text(2, 14, "95% interval 0 to 28%", ha="center", fontsize=9, color=MUTE)
    bars = b.bar(["plain", "netwing"], [11.0, 8.2], color=[GREY, TEAL])
    labels(b, bars, lambda v: f"{v:.1f}")
    b.set_ylim(0, 13.5)
    b.set_ylabel("mean tests per run")
    b.set_title("Tests used (budget 12)", loc="left", fontweight="bold")
    fig.suptitle("Hard suite, first-round run: simulator, Claude Haiku 5.5", x=0.01, ha="left", color=MUTE, fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "hard_suite.png", dpi=160)
    plt.close(fig)


def suites():
    fig, ax = plt.subplots(figsize=(9, 4.2))
    import numpy as np

    x = np.arange(3)
    plain = [11.0, 10.3, 6.9]
    netwing = [8.2, 7.0, 5.5]
    w = 0.36
    b1 = ax.bar(x - w / 2, plain, w, color=GREY, label="baseline (plain)")
    b2 = ax.bar(x + w / 2, netwing, w, color=TEAL, label="netwing")
    labels(ax, b1, lambda v: f"{v:.1f}")
    labels(ax, b2, lambda v: f"{v:.1f}")
    ax.set_xticks(x, ["Hard", "Multi-fault", "Easy"])
    ax.set_ylabel("mean tests per run")
    ax.set_ylim(0, 13)
    ax.legend(frameon=False, loc="upper right")
    ax.set_title("Tests used per run (simulator)", loc="left", fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "tests_used.png", dpi=160)
    plt.close(fig)


def second_fault():
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4.2))
    bars = a.bar(["without\ncoverage rule", "with\ncoverage rule"], [27, 98], color=[GREY, TEAL])
    labels(a, bars, lambda v: f"{v:.0f}%")
    a.set_ylim(0, 112)
    a.set_ylabel("both faults confirmed (%)")
    a.set_title("Second-fault confirmation (fresh6)", loc="left", fontweight="bold")
    a.text(0, 5, "16 of 60", ha="center", color=INK, fontsize=10)
    a.text(1, 5, "59 of 60", ha="center", color="white", fontsize=10)
    bars = b.bar(["without", "with"], [7.30, 8.32], color=[GREY, TEAL])
    labels(b, bars, lambda v: f"{v:.2f}")
    b.set_ylim(0, 10.5)
    b.set_ylabel("mean tests per run")
    b.set_title("Cost: about one extra test", loc="left", fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "second_fault.png", dpi=160)
    plt.close(fig)


def real_net():
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(["plain", "netwing"], [7.4, 5.6], color=[GREY, TEAL], width=0.5)
    labels(ax, bars, lambda v: f"{v:.1f}")
    ax.set_ylim(0, 9)
    ax.set_ylabel("mean tests per run")
    ax.set_title("Real Linux network (namespaces), easy suite", loc="left", fontweight="bold")
    ax.text(0.5, 8.2, "about 24 to 26% fewer tests", ha="center", color=TEAL, fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "real_network.png", dpi=160)
    plt.close(fig)


def architecture():
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 4.6)
    ax.axis("off")

    def box(x, y, w, h, text, fc, tc=INK, fs=11, bold=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=fc, ec=GREY, lw=1.2))
        ax.text(
            x + w / 2,
            y + h / 2,
            text,
            ha="center",
            va="center",
            fontsize=fs,
            color=tc,
            fontweight="bold" if bold else "normal",
        )

    def arrow(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14, color=INK, lw=1.4))

    box(0.2, 1.9, 1.5, 0.9, "Ticket", "#F3F4F6", bold=True)
    box(2.4, 1.9, 2.0, 0.9, "LLM agent\n(Claude + tools)", "#F3F4F6", bold=True)
    box(5.1, 1.2, 3.3, 2.3, "", "#E6F6F3")
    ax.text(6.75, 3.25, "NetWing controller", ha="center", fontsize=12, fontweight="bold", color=TEAL)
    for i, t in enumerate(
        [
            "numbered evidence ledger E1..En",
            "relevance, blip clearing",
            "confirmation + ping/DNS/port cover",
            "12-test budget, forced answer",
        ]
    ):
        ax.text(5.3, 2.8 - i * 0.42, "• " + t, fontsize=10, color=INK)
    box(9.1, 2.5, 1.7, 0.9, "STOP_FAULT\nSTOP_HEALTHY", "#FFF4DC", fs=10)
    box(9.1, 1.2, 1.7, 0.9, "CONTINUE\n(say what is missing)", "#F3F4F6", fs=10)
    box(2.4, 0.15, 2.0, 0.75, "Network backend\nsim | netns | kathara", "#F3F4F6", fs=10)
    arrow(1.7, 2.35, 2.4, 2.35)
    arrow(4.4, 2.5, 5.1, 2.5)
    arrow(8.4, 2.95, 9.1, 2.95)
    arrow(8.4, 1.65, 9.1, 1.65)
    arrow(3.4, 0.9, 3.4, 1.9)
    arrow(3.7, 1.9, 3.7, 0.9)
    ax.text(
        5.5, 0.5, "The rules are code, not a second model, so every decision can be audited.", fontsize=10, color=MUTE
    )
    fig.tight_layout()
    fig.savefig(OUT / "architecture.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    for f in (hard_suite, suites, second_fault, real_net, architecture):
        f()
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))
