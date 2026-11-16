"""Run the whole analysis: clean -> RFM segments -> holdout check -> Tableau files and charts.

    python run_analysis.py
"""
import pandas as pd

from retail import config, figures
from retail.clean import clean, load_raw
from retail.rfm import (cohort_retention, holdout_check, monthly_sales, rfm_table, score,
                        segment_summary)


def main():
    for d in (config.TABLEAU_DIR, config.TABLES_DIR, config.FIGURES_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print("Loading raw data (first run reads the Excel file and takes a few minutes)...")
    raw = load_raw()
    tx, log = clean(raw)
    log.to_csv(config.TABLES_DIR / "cleaning_log.csv", index=False)
    print(log.to_string(index=False))

    snapshot = tx["invoice_date"].max().normalize() + pd.Timedelta(days=1)
    customers = score(rfm_table(tx, snapshot))
    summary = segment_summary(customers)
    validation = holdout_check(tx, config.CALIBRATION_END, config.HOLDOUT_END)
    cohorts = cohort_retention(tx)
    monthly = monthly_sales(tx)
    # The data stops on 9 Dec 2011, so that month is partial. Flag it for Tableau rather than
    # let it look like a collapse in sales or retention.
    partial = tx["invoice_date"].max().to_period("M").to_timestamp()  # first day of the partial month
    monthly["complete_month"] = monthly["month"] < partial
    cal = cohorts["cohort"].dt.year * 12 + cohorts["cohort"].dt.month - 1 + cohorts["months_since_first"]
    cohorts["complete_month"] = cal < partial.year * 12 + partial.month - 1

    # Tableau data sources
    cols = ["customer_id", "country", "segment", "action", "rfm_code", "r_score", "f_score",
            "m_score", "recency_days", "frequency", "monetary", "avg_order_value",
            "first_purchase", "last_purchase"]
    customers[cols].rename(columns={"frequency": "orders", "monetary": "total_spend_gbp",
                                    "avg_order_value": "avg_order_value_gbp"}) \
        .to_csv(config.TABLEAU_DIR / "customers.csv", index=False, float_format="%.2f")
    summary.to_csv(config.TABLEAU_DIR / "segment_summary.csv", index=False, float_format="%.2f")
    cohorts.to_csv(config.TABLEAU_DIR / "cohort_retention.csv", index=False, float_format="%.2f")
    monthly.to_csv(config.TABLEAU_DIR / "monthly_sales.csv", index=False, float_format="%.2f")
    validation.to_csv(config.TABLES_DIR / "segment_holdout_validation.csv", index=False,
                      float_format="%.2f")

    figures.customers_vs_revenue(summary, config.FIGURES_DIR / "1_customers_vs_revenue.png")
    figures.holdout_repeat_rate(validation, config.FIGURES_DIR / "2_holdout_repeat_rate.png")
    figures.cohort_heatmap(cohorts, config.FIGURES_DIR / "3_cohort_retention.png")
    figures.monthly_revenue(monthly, config.FIGURES_DIR / "4_monthly_revenue.png")

    print(f"\nSnapshot date: {snapshot.date()}  |  customers: {len(customers):,}  |  "
          f"clean rows: {len(tx):,}  |  revenue: £{tx['revenue'].sum():,.0f}")
    print(f"Date range: {tx['invoice_date'].min().date()} to {tx['invoice_date'].max().date()}")
    print("\nSegments (full data):")
    print(summary.drop(columns="action").round(1).to_string(index=False))
    print("\nHoldout check (segments built on data to "
          f"{config.CALIBRATION_END}, behaviour to {config.HOLDOUT_END}):")
    print(validation.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
