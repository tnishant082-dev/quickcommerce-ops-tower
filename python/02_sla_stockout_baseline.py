#!/usr/bin/env python3
"""
Light SLA + stockout baseline on mart facts.
Not a production forecaster — just enough to show zone / SKU pressure and a seasonal-naive demand check.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MARTS = ROOT / "data" / "marts"
OUT = ROOT / "python" / "outputs"
REPORTS = ROOT / "reports"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    orders = pd.read_csv(MARTS / "fact_orders.csv", parse_dates=["order_date"])
    daily = pd.read_csv(MARTS / "mart_daily.csv", parse_dates=["order_date"])
    zone = pd.read_csv(MARTS / "mart_zone.csv")
    so = pd.read_csv(MARTS / "mart_top_stockout_skus.csv")

    delivered = orders[orders["is_delivered"] == 1].copy()

    # --- zone SLA ranking ---
    zone_rank = zone.sort_values("sla_hit_pct")
    worst = zone_rank.head(5)
    best = zone_rank.tail(5)

    # --- simple demand baseline: lag-7 seasonal naive on daily delivered orders ---
    d = daily.sort_values("order_date").copy()
    d["yhat"] = d["delivered_orders"].shift(7)
    hold = d.dropna(subset=["yhat"]).copy()
    hold["ape"] = (hold["delivered_orders"] - hold["yhat"]).abs() / hold["delivered_orders"].clip(lower=1)
    mape = float(hold["ape"].mean())

    # stockout concentration
    top10_share = float(so.head(10)["stockout_events"].sum() / so["stockout_events"].sum()) if len(so) else 0.0

    # evening vs morning SLA on delivered
    slot_sla = delivered.groupby("slot")["sla_hit"].mean().to_dict()

    metrics = {
        "demand_baseline": "seasonal_naive_lag7",
        "demand_mape": round(mape, 4),
        "holdout_days": int(len(hold)),
        "worst_zones": worst[["metro", "zone", "sla_hit_pct", "stockout_rate", "o2d_p50"]].to_dict("records"),
        "best_zones": best[["metro", "zone", "sla_hit_pct", "stockout_rate", "o2d_p50"]].to_dict("records"),
        "top10_sku_stockout_share": round(top10_share, 4),
        "slot_sla_hit_pct": {k: round(float(v), 4) for k, v in slot_sla.items()},
        "notes": [
            "Lag-7 naive is a baseline only — no weather / promo features.",
            "SLA gaps concentrate in a few zones (see worst_zones).",
            "Stockout events are head-heavy: top 10 SKUs drive a large share of events.",
        ],
    }
    (REPORTS / "sla_stockout_metrics.json").write_text(json.dumps(metrics, indent=2))
    (OUT / "sla_stockout_metrics.json").write_text(json.dumps(metrics, indent=2))

    # charts for notebook / portfolio
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    fig.patch.set_facecolor("#1B1A19")
    for ax in axes:
        ax.set_facecolor("#252423")
        ax.tick_params(colors="#94A3B8")
        for spine in ax.spines.values():
            spine.set_color("#40403D")

    ax = axes[0]
    plot_z = zone_rank.copy()
    ax.barh(plot_z["zone"], plot_z["sla_hit_pct"] * 100, color="#742774")
    ax.set_xlabel("SLA hit %", color="#F8FAFC")
    ax.set_title("Zone SLA hit % (ascending)", color="#F8FAFC", fontsize=11)
    ax.axvline(80, color="#F87171", ls="--", lw=1)

    ax = axes[1]
    top = so.head(12).iloc[::-1]
    ax.barh(top["sku_name"], top["stockout_events"], color="#A78BFA")
    ax.set_xlabel("Stockout events", color="#F8FAFC")
    ax.set_title("Top stockout SKUs", color="#F8FAFC", fontsize=11)

    fig.tight_layout()
    fig.savefig(OUT / "sla_stockout_baseline.png", dpi=140, facecolor=fig.get_facecolor())
    plt.close()

    # demand chart
    fig, ax = plt.subplots(figsize=(10, 3.8))
    fig.patch.set_facecolor("#1B1A19")
    ax.set_facecolor("#252423")
    ax.plot(hold["order_date"], hold["delivered_orders"], label="Actual", color="#60A5FA")
    ax.plot(hold["order_date"], hold["yhat"], label="Lag-7 naive", color="#742774", ls="--")
    ax.set_title(f"Delivered orders — seasonal naive (MAPE {mape*100:.1f}%)", color="#F8FAFC")
    ax.legend(facecolor="#252423", labelcolor="#F8FAFC")
    ax.tick_params(colors="#94A3B8")
    for spine in ax.spines.values():
        spine.set_color("#40403D")
    fig.tight_layout()
    fig.savefig(OUT / "demand_baseline.png", dpi=140, facecolor=fig.get_facecolor())
    plt.close()

    print(json.dumps({"mape": metrics["demand_mape"], "top10_share": metrics["top10_sku_stockout_share"]}, indent=2))


if __name__ == "__main__":
    main()
