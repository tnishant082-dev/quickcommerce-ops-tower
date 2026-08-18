#!/usr/bin/env python3
"""
Clean landing ops extracts → typed tables → analytics marts.
Run from repo root: python python/01_clean_ops_tables.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LANDING, CLEANED, MARTS = ROOT / "data" / "landing", ROOT / "data" / "cleaned", ROOT / "data" / "marts"
REPORTS = ROOT / "reports"


def log(m: str) -> None:
    print(m, flush=True)


def main() -> None:
    CLEANED.mkdir(parents=True, exist_ok=True)
    MARTS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    stores = pd.read_csv(LANDING / "dim_stores_raw.csv")
    skus = pd.read_csv(LANDING / "dim_skus_raw.csv")
    riders = pd.read_csv(LANDING / "dim_riders_raw.csv")
    orders = pd.read_csv(LANDING / "orders_raw.csv")
    lines = pd.read_csv(LANDING / "order_lines_raw.csv")
    stockouts = pd.read_csv(LANDING / "stockout_events_raw.csv")

    log(f"Landing load: orders={len(orders):,} lines={len(lines):,}")

    # --- cleaned: types + delivery flags ---
    o = orders.copy()
    o["ordered_at"] = pd.to_datetime(o["ordered_at"])
    o["order_date"] = pd.to_datetime(o["order_date"])
    # note: Partial still counts as delivered for GMV / SLA (customer received something)
    o["is_delivered"] = o["status"].isin(["Delivered", "Partial"]).astype(int)
    o["is_cancelled"] = (o["status"] == "Cancelled").astype(int)

    # basic quality gates before marts
    assert (o["gmv"] >= 0).all(), "negative GMV in landing"
    assert o["order_id"].is_unique, "duplicate order_id"

    stores.to_csv(CLEANED / "dim_stores.csv", index=False)
    skus.to_csv(CLEANED / "dim_skus.csv", index=False)
    riders.to_csv(CLEANED / "dim_riders.csv", index=False)
    o.to_csv(CLEANED / "fact_orders.csv", index=False)
    lines.to_csv(CLEANED / "fact_order_lines.csv", index=False)
    stockouts.to_csv(CLEANED / "fact_stockouts.csv", index=False)
    log("Cleaned tables written")

    # --- mart dims ---
    stores.to_csv(MARTS / "dim_store.csv", index=False)
    skus.to_csv(MARTS / "dim_sku.csv", index=False)
    riders.to_csv(MARTS / "dim_rider.csv", index=False)

    dates = pd.DataFrame({"order_date": pd.date_range(o["order_date"].min(), o["order_date"].max())})
    dates["date_key"] = dates["order_date"].dt.strftime("%Y%m%d").astype(int)
    dates["dow"] = dates["order_date"].dt.day_name()
    dates["is_weekend"] = dates["order_date"].dt.weekday.ge(5).astype(int)
    dates["week_num"] = dates["order_date"].dt.isocalendar().week.astype(int)
    dates.to_csv(MARTS / "dim_date.csv", index=False)

    fact = o.copy()
    fact["date_key"] = fact["order_date"].dt.strftime("%Y%m%d").astype(int)
    fact["gross_margin"] = fact["net_gmv"] - fact["cogs"]
    fact.to_csv(MARTS / "fact_orders.csv", index=False)
    lines.to_csv(MARTS / "fact_order_lines.csv", index=False)
    stockouts.to_csv(MARTS / "fact_stockouts.csv", index=False)

    delivered = fact[fact["is_delivered"] == 1]
    cancelled = fact[fact["is_cancelled"] == 1]

    mart_daily = fact.groupby("order_date", as_index=False).agg(
        orders=("order_id", "count"),
        delivered_orders=("is_delivered", "sum"),
        cancelled_orders=("is_cancelled", "sum"),
        gmv=("gmv", "sum"),
        net_gmv=("net_gmv", "sum"),
        discount_amount=("discount_amount", "sum"),
        sla_hits=("sla_hit", "sum"),
        stockout_orders=("had_stockout", "sum"),
    )
    mart_daily["order_date"] = mart_daily["order_date"].dt.strftime("%Y-%m-%d")
    mart_daily["aov"] = mart_daily["gmv"] / mart_daily["delivered_orders"].clip(lower=1)
    mart_daily["sla_hit_pct"] = mart_daily["sla_hits"] / mart_daily["delivered_orders"].clip(lower=1)
    mart_daily["cancel_pct"] = mart_daily["cancelled_orders"] / mart_daily["orders"]
    mart_daily["stockout_rate"] = mart_daily["stockout_orders"] / mart_daily["orders"]
    o2d_daily = (
        delivered.groupby(delivered["order_date"].dt.strftime("%Y-%m-%d"))["o2d_minutes"]
        .agg(o2d_p50=lambda s: float(np.percentile(s.dropna(), 50)), o2d_p90=lambda s: float(np.percentile(s.dropna(), 90)))
        .reset_index()
    )
    o2d_daily.columns = ["order_date", "o2d_p50", "o2d_p90"]
    mart_daily = mart_daily.merge(o2d_daily, on="order_date", how="left")
    mart_daily.to_csv(MARTS / "mart_daily.csv", index=False)

    def pctile(s, q):
        s = s.dropna()
        return float(np.percentile(s, q)) if len(s) else np.nan

    mart_store = fact.groupby(["store_id", "metro", "zone"], as_index=False).agg(
        orders=("order_id", "count"),
        delivered_orders=("is_delivered", "sum"),
        cancelled_orders=("is_cancelled", "sum"),
        gmv=("gmv", "sum"),
        net_gmv=("net_gmv", "sum"),
        sla_hits=("sla_hit", "sum"),
        stockout_orders=("had_stockout", "sum"),
        o2d_p50=("o2d_minutes", lambda s: pctile(s, 50)),
        o2d_p90=("o2d_minutes", lambda s: pctile(s, 90)),
    )
    mart_store["sla_hit_pct"] = mart_store["sla_hits"] / mart_store["delivered_orders"].clip(lower=1)
    mart_store["cancel_pct"] = mart_store["cancelled_orders"] / mart_store["orders"]
    mart_store["stockout_rate"] = mart_store["stockout_orders"] / mart_store["orders"]
    mart_store["aov"] = mart_store["gmv"] / mart_store["delivered_orders"].clip(lower=1)
    mart_store.to_csv(MARTS / "mart_store.csv", index=False)

    mart_zone = fact.groupby(["metro", "zone"], as_index=False).agg(
        orders=("order_id", "count"),
        gmv=("gmv", "sum"),
        sla_hit_pct=("sla_hit", "mean"),
        cancel_pct=("is_cancelled", "mean"),
        stockout_rate=("had_stockout", "mean"),
        o2d_p50=("o2d_minutes", lambda s: pctile(s, 50)),
    )
    mart_zone.to_csv(MARTS / "mart_zone.csv", index=False)

    so_sku = (
        stockouts.merge(skus, on="sku_id")
        .groupby(["sku_id", "sku_name", "category"], as_index=False)
        .size()
        .rename(columns={"size": "stockout_events"})
        .sort_values("stockout_events", ascending=False)
    )
    so_sku.head(50).to_csv(MARTS / "mart_top_stockout_skus.csv", index=False)

    promo = fact.groupby("promo_type", as_index=False).agg(
        orders=("order_id", "count"),
        delivered=("is_delivered", "sum"),
        gmv=("gmv", "sum"),
        discount_amount=("discount_amount", "sum"),
        net_gmv=("net_gmv", "sum"),
        cancel_pct=("is_cancelled", "mean"),
    )
    promo["promo_burn_pct"] = promo["discount_amount"] / promo["gmv"].clip(lower=1)
    base_aov = delivered.loc[delivered["promo_type"] == "None", "gmv"].mean()
    promo["aov"] = promo["gmv"] / promo["delivered"].clip(lower=1)
    promo["aov_lift_vs_none"] = promo["aov"] - base_aov
    promo["promo_roi_proxy"] = np.where(
        promo["discount_amount"] > 0,
        (promo["net_gmv"] - promo["delivered"] * (base_aov * 0.85)) / promo["discount_amount"],
        np.nan,
    )
    promo.to_csv(MARTS / "mart_promo.csv", index=False)

    rider_orders = (
        delivered.dropna(subset=["rider_id"])
        .groupby("rider_id", as_index=False)
        .agg(deliveries=("order_id", "count"), avg_o2d=("o2d_minutes", "mean"), sla_hit_pct=("sla_hit", "mean"))
        .merge(riders, on="rider_id", how="left")
    )
    n_days = (fact["order_date"].max() - fact["order_date"].min()).days + 1
    rider_orders["util_pct"] = (rider_orders["deliveries"] / (n_days * 6 * 2.5)).clip(upper=1.2)
    rider_orders.to_csv(MARTS / "mart_rider.csv", index=False)

    slot_w = fact.groupby(["slot", "weather"], as_index=False).agg(
        orders=("order_id", "count"),
        sla_hit_pct=("sla_hit", "mean"),
        o2d_p50=("o2d_minutes", lambda s: pctile(s, 50)),
        cancel_pct=("is_cancelled", "mean"),
    )
    slot_w.to_csv(MARTS / "mart_slot_weather.csv", index=False)

    cancelled.groupby("cancel_reason", as_index=False).size().rename(columns={"size": "cancels"}).sort_values(
        "cancels", ascending=False
    ).to_csv(MARTS / "mart_cancel_reason.csv", index=False)

    o2d_vals = delivered["o2d_minutes"].dropna()
    kpi = {
        "window_start": str(fact["order_date"].min().date()),
        "window_end": str(fact["order_date"].max().date()),
        "dark_stores": int(stores.shape[0]),
        "skus": int(skus.shape[0]),
        "riders": int(riders.shape[0]),
        "orders": int(fact.shape[0]),
        "delivered_orders": int(delivered.shape[0]),
        "cancelled_orders": int(cancelled.shape[0]),
        "gmv_inr": round(float(delivered["gmv"].sum()), 2),
        "net_gmv_inr": round(float(delivered["net_gmv"].sum()), 2),
        "aov_inr": round(float(delivered["gmv"].sum() / max(len(delivered), 1)), 2),
        "o2d_p50_min": round(float(np.percentile(o2d_vals, 50)), 2),
        "o2d_p90_min": round(float(np.percentile(o2d_vals, 90)), 2),
        "sla_hit_pct": round(float(delivered["sla_hit"].mean()), 4),
        "stockout_rate": round(float(fact["had_stockout"].mean()), 4),
        "cancel_pct": round(float(fact["is_cancelled"].mean()), 4),
        "promo_burn_inr": round(float(delivered["discount_amount"].sum()), 2),
        "promo_burn_pct_of_gmv": round(float(delivered["discount_amount"].sum() / max(delivered["gmv"].sum(), 1)), 4),
        "rider_util_median": round(float(rider_orders["util_pct"].median()), 4),
        "gross_margin_inr": round(float(delivered["gross_margin"].sum()), 2),
        "top_failing_zone": mart_zone.sort_values("sla_hit_pct").iloc[0]["zone"],
        "top_failing_zone_sla": round(float(mart_zone.sort_values("sla_hit_pct").iloc[0]["sla_hit_pct"]), 4),
        "top_stockout_sku": so_sku.iloc[0]["sku_name"],
        "top_stockout_events": int(so_sku.iloc[0]["stockout_events"]),
    }
    (REPORTS / "kpi_summary.json").write_text(json.dumps(kpi, indent=2))
    (MARTS / "metrics_summary.json").write_text(json.dumps(kpi, indent=2))
    log(f"Marts ready. Orders={kpi['orders']:,} SLA={kpi['sla_hit_pct']*100:.1f}% GMV=₹{kpi['gmv_inr']:,.0f}")


if __name__ == "__main__":
    main()
