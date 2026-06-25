from __future__ import annotations

from datetime import date, datetime
from numbers import Real
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib import font_manager

STOCK_KEYS = {
    "NIKKEI225",
    "TOPIX",
    "DOW",
    "SP500",
    "NASDAQ",
    "RUSSELL2000",
    "FTSE100",
    "DAX",
    "CAC40",
    "HANGSENG",
    "SHANGHAI",
    "KOSPI",
}
FX_COMMODITY_KEYS = {"USDJPY", "EURJPY", "EURUSD", "DXY", "DOLLAR_BROAD", "GOLD", "WTI"}
RISK_RATE_KEYS = {"US10Y", "SOFR", "VIX", "YIELD_2S10S"}
PREFERRED_KEYS = [
    "NIKKEI225",
    "TOPIX",
    "DOW",
    "SP500",
    "NASDAQ",
    "RUSSELL2000",
    "USDJPY",
    "EURUSD",
    "GOLD",
    "WTI",
    "US10Y",
    "SOFR",
    "VIX",
    "YIELD_2S10S",
    "DOLLAR_BROAD",
]
COLORS = ["#38bdf8", "#f97316", "#22c55e", "#f472b6", "#a78bfa", "#06b6d4", "#facc15", "#cbd5e1"]


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
    by_key = {entry["item"].get("key"): entry for entry in prepared}
    ordered = [by_key[key] for key in PREFERRED_KEYS if key in by_key]
    ordered.extend(entry for entry in prepared if entry not in ordered)
    return ordered


def _numeric_change(item: dict[str, Any]) -> float | None:
    value = item.get("change_pct")
    if isinstance(value, Real):
        return float(value)
    return None


def _split_groups(chart_items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {"stocks": [], "fx_commodity": [], "risk_rate": [], "other": []}
    for entry in chart_items:
        key = str(entry["item"].get("key", ""))
        if key in STOCK_KEYS:
            groups["stocks"].append(entry)
        elif key in FX_COMMODITY_KEYS:
            groups["fx_commodity"].append(entry)
        elif key in RISK_RATE_KEYS:
            groups["risk_rate"].append(entry)
        else:
            groups["other"].append(entry)
    return groups


def _normalize(points: list[tuple[date, float]]) -> tuple[list[date], list[float]]:
    raw_values = [value for _, value in points]
    base_value = raw_values[0] if raw_values and raw_values[0] else 1
    return [point_date for point_date, _ in points], [(value / base_value) * 100 for value in raw_values]


def _format_value(item: dict[str, Any]) -> str:
    current = item.get("current")
    unit = item.get("unit", "")
    if current is None:
        return "未確認"
    return f"{current:,.2f}{unit}"


def _format_change(value: float | None) -> str:
    if value is None:
        return "未確認"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.2f}%"


def _setup_fonts() -> None:
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


def _style_axis(ax: Any) -> None:
    ax.set_facecolor("#0b1624")
    ax.tick_params(axis="x", colors="#dbeafe", labelsize=14, pad=8)
    ax.tick_params(axis="y", colors="#dbeafe", labelsize=14, pad=8)
    for spine in ax.spines.values():
        spine.set_color("#3b82f6")
        spine.set_alpha(0.35)
    ax.grid(True, alpha=0.46, color="#21344f", linewidth=1.1)


def _set_date_axis(ax: Any) -> None:
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))


def _draw_line_panel(ax: Any, title: str, entries: list[dict[str, Any]], max_lines: int = 7) -> None:
    _style_axis(ax)
    ax.set_title(title, color="#f8fafc", fontsize=21, fontweight="bold", pad=14, loc="left")
    if not entries:
        ax.text(0.5, 0.5, "取得できたデータがありません", color="#bfdbfe", ha="center", va="center", transform=ax.transAxes, fontsize=16)
        return

    plotted = entries[:max_lines]
    min_value = 100.0
    max_value = 100.0
    for index, entry in enumerate(plotted):
        item = entry["item"]
        x_values, y_values = _normalize(entry["points"])
        if not y_values:
            continue
        min_value = min(min_value, min(y_values))
        max_value = max(max_value, max(y_values))
        color = COLORS[index % len(COLORS)]
        label = f"{item.get('label', item.get('key', '未確認'))} {_format_change(_numeric_change(item))}"
        ax.plot(x_values, y_values, marker="o", markersize=6.5, linewidth=3.2, label=label, color=color)

    span = max(max_value - min_value, 1.0)
    ax.set_ylim(min_value - span * 0.22, max_value + span * 0.24)
    ax.axhline(100, color="#93c5fd", linewidth=1.4, alpha=0.9)
    _set_date_axis(ax)
    legend_columns = 2 if len(plotted) <= 4 else 3
    ax.legend(
        facecolor="#10243a",
        edgecolor="#3b82f6",
        labelcolor="#f8fafc",
        fontsize=12,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=legend_columns,
        framealpha=0.96,
        borderpad=0.65,
        columnspacing=1.15,
        handlelength=2.1,
    )


def _draw_bar_panel(ax: Any, entries: list[dict[str, Any]]) -> None:
    _style_axis(ax)
    ranked_items = [entry["item"] for entry in entries if _numeric_change(entry["item"]) is not None]
    ranked_items.sort(key=lambda item: _numeric_change(item) or 0, reverse=True)
    ranked_items = ranked_items[:10]
    ax.set_title("4. 前日比ランキング（取得値のみ）", color="#f8fafc", fontsize=21, fontweight="bold", pad=14, loc="left")
    if not ranked_items:
        ax.text(0.5, 0.5, "前日比は未確認です", color="#bfdbfe", ha="center", va="center", transform=ax.transAxes, fontsize=16)
        return

    labels = [item.get("label", item.get("key", "未確認")) for item in ranked_items]
    changes = [_numeric_change(item) or 0 for item in ranked_items]
    bar_colors = ["#22c55e" if value >= 0 else "#ef4444" for value in changes]
    positions = list(range(len(labels)))
    ax.barh(positions, changes, color=bar_colors, alpha=0.92, height=0.58)
    ax.set_yticks(positions, labels=labels)
    ax.invert_yaxis()
    ax.axvline(0, color="#dbeafe", linewidth=1.4)
    max_abs = max([abs(value) for value in changes] + [1.0])
    ax.set_xlim(-max_abs * 1.24, max_abs * 1.24)
    for index, value in enumerate(changes):
        ax.text(
            value + (max_abs * 0.025 if value >= 0 else -max_abs * 0.025),
            index,
            _format_change(value),
            color="#f8fafc",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=13,
            fontweight="bold",
        )


def create_market_chart(
    task_id: str,
    task_config: dict[str, Any],
    raw_data: dict[str, Any],
    rules: dict[str, Any],
    output_dir: Path,
) -> Path | None:
    chart_items = _prepare_chart_items(raw_data)
    if not chart_items:
        return None

    _setup_fonts()
    width = rules.get("common", {}).get("chart_width", 1280) / 100
    height = max(rules.get("common", {}).get("chart_height", 720) / 100, 16.2)
    fig, axes = plt.subplots(
        4,
        1,
        figsize=(width, height),
        dpi=100,
        gridspec_kw={"height_ratios": [1.55, 1.35, 1.25, 1.45]},
    )
    fig.patch.set_facecolor("#07111e")

    groups = _split_groups(chart_items)
    stock_entries = groups["stocks"] or chart_items[:7]
    fx_entries = groups["fx_commodity"] + groups["other"]
    risk_entries = groups["risk_rate"]

    title = task_config.get("title", task_id)
    fig.suptitle(f"{title}\n直近6取得日ダッシュボード", color="#f8fafc", fontsize=26, fontweight="bold", y=0.997)
    _draw_line_panel(axes[0], "1. 株価指数: 同じ種類だけで比較（初日=100）", stock_entries, max_lines=6)
    _draw_line_panel(axes[1], "2. 為替・商品: 外部環境の方向（初日=100）", fx_entries, max_lines=5)
    _draw_line_panel(axes[2], "3. 金利・VIX: リスク温度計（初日=100）", risk_entries, max_lines=4)
    _draw_bar_panel(axes[3], chart_items)

    path = output_dir / f"{task_id}_chart.png"
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.text(
        0.012,
        0.008,
        "データは取得できた終値のみ使用。未取得日は補完せず、種類の違う指標は別パネルで表示。",
        color="#94a3b8",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0.026, 1, 0.956), h_pad=4.1)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path
