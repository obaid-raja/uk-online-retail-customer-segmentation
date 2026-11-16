"""Recency, Frequency, Monetary scoring and segmentation."""
import re

import numpy as np
import pandas as pd

from . import config


def rfm_table(tx: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    """One row per customer.

    recency_days: days from last purchase to the snapshot date (lower is better)
    frequency:    number of separate orders (invoices)
    monetary:     total spend in GBP
    """
    g = tx.groupby("customer_id")
    out = pd.DataFrame({
        "first_purchase": g["invoice_date"].min(),
        "last_purchase": g["invoice_date"].max(),
        "frequency": g["invoice"].nunique(),
        "monetary": g["revenue"].sum(),
        "country": g["country"].agg(lambda s: s.mode().iat[0]),
    })
    out["recency_days"] = (snapshot.normalize() - out["last_purchase"].dt.normalize()).dt.days
    out["avg_order_value"] = out["monetary"] / out["frequency"]
    return out.reset_index()


def band(values: pd.Series, higher_is_better: bool = True, n: int = config.N_BANDS) -> pd.Series:
    """Split customers into n equal-sized bands, scored 1 (worst) to n (best).

    Ranking first (ties broken by order) keeps the bands equal-sized even when
    many customers share a value, e.g. the large group with exactly one order.
    """
    ranks = values.rank(method="first", ascending=higher_is_better)
    return pd.qcut(ranks, n, labels=range(1, n + 1)).astype(int)


def segment_of(rf_code: str) -> str:
    for pattern, name in config.SEGMENT_MAP.items():
        if re.fullmatch(pattern, rf_code):
            return name
    raise ValueError(f"No segment for RF code {rf_code}")


def score(rfm: pd.DataFrame) -> pd.DataFrame:
    out = rfm.copy()
    out["r_score"] = band(out["recency_days"], higher_is_better=False)
    out["f_score"] = band(out["frequency"])
    out["m_score"] = band(out["monetary"])
    out["rfm_code"] = (out["r_score"].astype(str) + out["f_score"].astype(str)
                       + out["m_score"].astype(str))
    out["segment"] = [segment_of(c[:2]) for c in out["rfm_code"]]
    out["action"] = out["segment"].map(config.SEGMENT_ACTION)
    return out


def segment_summary(scored: pd.DataFrame) -> pd.DataFrame:
    g = scored.groupby("segment")
    s = pd.DataFrame({
        "customers": g.size(),
        "revenue_gbp": g["monetary"].sum(),
        "avg_recency_days": g["recency_days"].mean(),
        "avg_orders": g["frequency"].mean(),
        "avg_spend_gbp": g["monetary"].mean(),
        "avg_order_value_gbp": g["avg_order_value"].mean(),
    })
    s["share_of_customers_pct"] = 100 * s["customers"] / s["customers"].sum()
    s["share_of_revenue_pct"] = 100 * s["revenue_gbp"] / s["revenue_gbp"].sum()
    s["action"] = s.index.map(config.SEGMENT_ACTION)
    order = [x for x in config.SEGMENT_ORDER if x in s.index]
    return s.loc[order].reset_index()


def holdout_check(tx: pd.DataFrame, calibration_end: str, holdout_end: str) -> pd.DataFrame:
    """Do the segments predict future behaviour?

    Segments are built only from purchases up to calibration_end; we then look at
    what each customer actually bought in the holdout window that follows.
    """
    cal_end = pd.Timestamp(calibration_end)
    hold_end = pd.Timestamp(holdout_end) + pd.Timedelta(days=1)
    cal = tx[tx["invoice_date"] < cal_end]
    hold = tx[(tx["invoice_date"] >= cal_end) & (tx["invoice_date"] < hold_end)]

    scored = score(rfm_table(cal, cal_end))
    future = hold.groupby("customer_id")["revenue"].sum()
    scored["holdout_spend"] = scored["customer_id"].map(future).fillna(0.0)
    scored["bought_again"] = scored["holdout_spend"] > 0

    g = scored.groupby("segment")
    v = pd.DataFrame({
        "customers": g.size(),
        "bought_again_pct": 100 * g["bought_again"].mean(),
        "avg_holdout_spend_gbp": g["holdout_spend"].mean(),
        "holdout_revenue_gbp": g["holdout_spend"].sum(),
    })
    v["share_of_holdout_revenue_pct"] = 100 * v["holdout_revenue_gbp"] / v["holdout_revenue_gbp"].sum()
    order = [x for x in config.SEGMENT_ORDER if x in v.index]
    overall = pd.DataFrame({
        "customers": [len(scored)],
        "bought_again_pct": [100 * scored["bought_again"].mean()],
        "avg_holdout_spend_gbp": [scored["holdout_spend"].mean()],
        "holdout_revenue_gbp": [scored["holdout_spend"].sum()],
        "share_of_holdout_revenue_pct": [100.0],
    }, index=["All customers"])
    return pd.concat([v.loc[order], overall]).rename_axis("segment").reset_index()


def cohort_retention(tx: pd.DataFrame) -> pd.DataFrame:
    """Monthly acquisition cohorts: share of each cohort that ordered again n months later.

    Long format (one row per cohort x month) so Tableau can build a heatmap directly.
    """
    month = tx["invoice_date"].dt.to_period("M")
    first = month.groupby(tx["customer_id"]).transform("min")
    d = pd.DataFrame({"customer_id": tx["customer_id"], "cohort": first, "month": month})
    d = d.drop_duplicates()
    d["months_since_first"] = (d["month"] - d["cohort"]).apply(lambda x: x.n)
    counts = d.groupby(["cohort", "months_since_first"])["customer_id"].nunique().rename("customers")
    counts = counts.reset_index()
    size = counts[counts["months_since_first"] == 0].set_index("cohort")["customers"]
    counts["cohort_size"] = counts["cohort"].map(size)
    counts["retention_pct"] = 100 * counts["customers"] / counts["cohort_size"]
    counts["cohort"] = counts["cohort"].dt.to_timestamp()
    return counts


def monthly_sales(tx: pd.DataFrame) -> pd.DataFrame:
    """Monthly revenue, orders and active customers, split UK vs international."""
    d = tx.assign(
        month=tx["invoice_date"].dt.to_period("M").dt.to_timestamp(),
        market=np.where(tx["country"] == "United Kingdom", "UK", "International"),
    )
    first_month = d.groupby("customer_id")["month"].transform("min")
    d["is_new"] = d["month"] == first_month
    g = d.groupby(["month", "market"])
    out = pd.DataFrame({
        "revenue_gbp": g["revenue"].sum(),
        "orders": g["invoice"].nunique(),
        "active_customers": g["customer_id"].nunique(),
    })
    new = d[d["is_new"]].groupby(["month", "market"])["customer_id"].nunique()
    out["new_customers"] = new.reindex(out.index).fillna(0).astype(int)
    return out.reset_index()
