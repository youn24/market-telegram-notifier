from __future__ import annotations

from datetime import date, datetime
from numbers import Real
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _chart_points(item: dict[str, Any]) -> list[tuple[date, float]]:
    points_by_date: dict[date, float] = {}
    for point in item.get("series", []):
        point_date = _parse_date(point.get("date"))
        raw_value = point.get("value")
        if point_date is None or raw_value is None:
            continue
        try:
            points_by_date[point_date] = float(raw_value)
        except (TypeError, ValueError):
            continue
    return sorted(points_by_date.items(), key=lambda pair: pair[0])


def _prepare_chart_items(raw_data: dict[str, Any]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for item in raw_data.get("items", []) + raw_data.get("macro_items", []):
        points = _chart_points(item)
        if len(points) >= 2:
            prepared.append({"item": item, "points": points})
    return prepared


def _numeric_change(item: dict[str, Any]) -> float | None:
    value = item.get("change_pct")
    if isinstance(value, Real):
        return float(value)
    return None


def create_market_chart(
    task_id: str,
    task_config: dict[str, Any],
    raw_data: dict[str, Any],
    rules: dict[str, Any],
    output_dir: Path,
) -> Path | None:
    available_items = _prepare_chart_items(raw_data)
    preferred_keys = ["NIKKEI225", "TOPIX", "SP500", "NASDAQ", "USDJPY", "US10Y", "VIX", "DOLLAR_BROAD"]
    by_key = {entry["item"].get("key"): entry for entry in available_items}
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

    fig, axes = plt.subplots(2, 1, figsize=(width, height), dpi=100, gridspec_kw={"height_ratios": [2.15, 1]})
    fig.patch.set_facecolor("#07111e")
    ax = axes[0]
    bar_ax = axes[1]
    ax.set_facecolor("#0b1624")
    bar_ax.set_facecolor("#0b1624")

    colors = ["#38bdf8", "#f97316", "#22c55e", "#ec4899", "#8b5cf6", "#06b6d4", "#facc15", "#cbd5e1"]

    for index, entry in enumerate(chart_items):
        item = entry["item"]
        points = entry["points"]
        x_values = [point_date for point_date, _ in points]
        raw_values = [value for _, value in points]
        base_value = raw_values[0] if raw_values and raw_values[0] else 1
        y_values = [(value / base_value) * 100 for value in raw_values]
        ax.plot(x_values, y_values, marker="o", markersize=7, linewidth=3.8, label=item["label"], color=colors[index % len(colors)])

    ax.set_title(f"{task_config.get('title', task_id)} 日足比較（初日=100）", color="#f8fafc", fontsize=25, fontweight="bold", pad=20)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.tick_params(axis="x", colors="#cbd5e1", rotation=0, labelsize=15)
    ax.tick_params(axis="y", colors="#cbd5e1", labelsize=16)
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.grid(True, alpha=0.42, color="#203044", linewidth=1.1)
    ax.legend(facecolor="#10243a", edgecolor="#334155", labelcolor="#f8fafc", fontsize=13, loc="upper left", framealpha=0.94)

    ranked_items = [
        entry["item"]
        for entry in chart_items
        if _numeric_change(entry["item"]) is not None
    ]
    ranked_items.sort(key=lambda item: _numeric_change(item) or 0, reverse=True)
    labels = [item["label"] for item in ranked_items]
    changes = [_numeric_change(item) or 0 for item in ranked_items]
    bar_colors = ["#22c55e" if value >= 0 else "#ef4444" for value in changes]
    positions = list(range(len(labels)))
    bar_ax.barh(positions, changes, color=bar_colors, alpha=0.92, height=0.56)
    bar_ax.set_yticks(positions, labels=labels)
    bar_ax.invert_yaxis()
    bar_ax.tick_params(axis="y", colors="#e5e7eb", labelsize=15)
    bar_ax.tick_params(axis="x", colors="#cbd5e1", labelsize=14)
    bar_ax.axvline(0, color="#94a3b8", linewidth=1.4)
    max_abs = max([abs(value) for value in changes] + [1.0])
    bar_ax.set_xlim(-max_abs * 1.22, max_abs * 1.22)
    bar_ax.set_title("前日比ランキング", color="#f8fafc", fontsize=21, fontweight="bold", pad=16)
    for spine in bar_ax.spines.values():
        spine.set_color("#334155")
    bar_ax.grid(True, axis="x", alpha=0.38, color="#203044", linewidth=1.1)
    for index, value in enumerate(changes):
        prefix = "+" if value > 0 else ""
        bar_ax.text(
            value + (0.05 if value >= 0 else -0.05),
            index,
            f"{prefix}{value:.2f}%",
            color="#f8fafc",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=14,
            fontweight="bold",
        )

    path = output_dir / f"{task_id}_chart.png"
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.text(
        0.012,
        0.012,
        "横軸は実日付順。休場日・未取得日は飛ばさず、取得できた日足だけを描画。",
        color="#94a3b8",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path
