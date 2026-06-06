from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def create_market_chart(
    task_id: str,
    task_config: dict[str, Any],
    raw_data: dict[str, Any],
    rules: dict[str, Any],
    output_dir: Path,
) -> Path | None:
    chart_items = [item for item in raw_data.get("items", []) if item.get("series")]
    if not chart_items:
        return None

    width = rules.get("common", {}).get("chart_width", 1280) / 100
    height = rules.get("common", {}).get("chart_height", 720) / 100

    fig, ax = plt.subplots(figsize=(width, height), dpi=100)
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")

    colors = ["#38bdf8", "#f59e0b", "#34d399", "#f472b6", "#a78bfa"]

    for index, item in enumerate(chart_items):
        series = item["series"]
        x_values = [point["date"] for point in series]
        y_values = [point["value"] for point in series]
        ax.plot(x_values, y_values, marker="o", linewidth=2.2, label=item["label"], color=colors[index % len(colors)])

    ax.set_title(task_config.get("title", task_id), color="white", fontsize=18, pad=18)
    ax.tick_params(axis="x", colors="#cbd5e1", rotation=20)
    ax.tick_params(axis="y", colors="#cbd5e1")
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.grid(True, alpha=0.18, color="#94a3b8")
    ax.legend(facecolor="#111827", edgecolor="#334155", labelcolor="white")

    path = output_dir / f"{task_id}_chart.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path
