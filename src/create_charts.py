from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager


def create_market_chart(
    task_id: str,
    task_config: dict[str, Any],
    raw_data: dict[str, Any],
    rules: dict[str, Any],
    output_dir: Path,
) -> Path | None:
    available_items = [item for item in raw_data.get("items", []) + raw_data.get("macro_items", []) if item.get("series")]
    preferred_keys = ["NIKKEI225", "TOPIX", "SP500", "NASDAQ", "USDJPY", "US10Y", "VIX", "DOLLAR_BROAD"]
    by_key = {item.get("key"): item for item in available_items}
    chart_items = [by_key[key] for key in preferred_keys if key in by_key]
    chart_items.extend(item for item in available_items if item not in chart_items)
    chart_items = chart_items[:8]
    if not chart_items:
        return None

    width = rules.get("common", {}).get("chart_width", 1280) / 100
    height = rules.get("common", {}).get("chart_height", 720) / 100

    for font_path in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
    ]:
        try:
            font_manager.fontManager.addfont(font_path)
        except Exception:
            continue
    plt.rcParams["font.family"] = ["Noto Sans CJK JP", "Meiryo", "Yu Gothic", "DejaVu Sans"]

    fig, axes = plt.subplots(2, 1, figsize=(width, height), dpi=100, gridspec_kw={"height_ratios": [2, 1]})
    fig.patch.set_facecolor("#0f172a")
    ax = axes[0]
    bar_ax = axes[1]
    ax.set_facecolor("#0f172a")
    bar_ax.set_facecolor("#0f172a")

    colors = ["#38bdf8", "#f59e0b", "#34d399", "#f472b6", "#a78bfa"]

    for index, item in enumerate(chart_items):
        series = item["series"]
        x_values = [point["date"] for point in series]
        raw_values = [point["value"] for point in series]
        base_value = raw_values[0] if raw_values and raw_values[0] else 1
        y_values = [(value / base_value) * 100 for value in raw_values]
        ax.plot(x_values, y_values, marker="o", linewidth=2.2, label=item["label"], color=colors[index % len(colors)])

    ax.set_title(f"{task_config.get('title', task_id)} 日足比較(初日=100)", color="white", fontsize=22, pad=18)
    ax.tick_params(axis="x", colors="#cbd5e1", rotation=0, labelsize=14)
    ax.tick_params(axis="y", colors="#cbd5e1", labelsize=14)
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.grid(True, alpha=0.18, color="#94a3b8")
    ax.legend(facecolor="#111827", edgecolor="#334155", labelcolor="white", fontsize=12, loc="upper left")

    labels = [item["label"] for item in chart_items]
    changes = [item.get("change_pct") or 0 for item in chart_items]
    bar_colors = ["#22c55e" if value >= 0 else "#ef4444" for value in changes]
    positions = list(range(len(labels)))
    bar_ax.barh(positions, changes, color=bar_colors, alpha=0.92, height=0.56)
    bar_ax.set_yticks(positions, labels=labels)
    bar_ax.tick_params(axis="y", colors="#e2e8f0", labelsize=14)
    bar_ax.tick_params(axis="x", colors="#cbd5e1", labelsize=13)
    bar_ax.axvline(0, color="#94a3b8", linewidth=1)
    bar_ax.set_title("前日比", color="white", fontsize=18, pad=14)
    for spine in bar_ax.spines.values():
        spine.set_color("#334155")
    bar_ax.grid(True, axis="x", alpha=0.18, color="#94a3b8")
    for index, value in enumerate(changes):
        prefix = "+" if value > 0 else ""
        bar_ax.text(value + (0.05 if value >= 0 else -0.05), index, f"{prefix}{value:.2f}%", color="white", va="center", ha="left" if value >= 0 else "right", fontsize=13)

    path = output_dir / f"{task_id}_chart.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path
