"""Paths and analysis settings. Change values here, not inside the code."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_XLSX = ROOT / "data" / "raw" / "online_retail_II.xlsx"
RAW_CACHE = ROOT / "data" / "interim" / "transactions_raw.csv.gz"
TABLEAU_DIR = ROOT / "outputs" / "tableau"
TABLES_DIR = ROOT / "outputs" / "tables"
FIGURES_DIR = ROOT / "outputs" / "figures"

# Real products have a five-digit stock code (optionally followed by letters).
# Everything else is postage, fees, manual adjustments or tests.
PRODUCT_CODE_PATTERN = r"^\d{5}"

# Validation split: build segments on data up to CALIBRATION_END, then check
# who actually bought in the following six months (the holdout).
CALIBRATION_END = "2011-06-09"
HOLDOUT_END = "2011-12-09"

# Number of score bands for R, F and M (quintiles).
N_BANDS = 5

# Standard RFM segment map on the Recency and Frequency scores (both 1-5, 5 = best).
# Each regex matches the two-digit "RF" code.
SEGMENT_MAP = {
    r"5[4-5]": "Champions",
    r"[3-4][4-5]": "Loyal customers",
    r"[4-5][2-3]": "Potential loyalists",
    r"51": "New customers",
    r"41": "Promising",
    r"33": "Need attention",
    r"3[1-2]": "About to sleep",
    r"[1-2]5": "Can't lose",
    r"[1-2][3-4]": "At risk",
    r"[1-2][1-2]": "Hibernating",
}

# Display order: most valuable and engaged first.
SEGMENT_ORDER = [
    "Champions",
    "Loyal customers",
    "Potential loyalists",
    "New customers",
    "Promising",
    "Need attention",
    "About to sleep",
    "Can't lose",
    "At risk",
    "Hibernating",
]

# What a marketing team would do with each segment.
SEGMENT_ACTION = {
    "Champions": "Reward; early access to new ranges; ask for reviews",
    "Loyal customers": "Upsell higher-value ranges; loyalty scheme",
    "Potential loyalists": "Membership offer; recommend related products",
    "New customers": "Onboarding emails; make the second order easy",
    "Promising": "Build awareness of the wider range; small incentive",
    "Need attention": "Time-limited, personalised offer",
    "About to sleep": "Reactivation email with popular products",
    "Can't lose": "Personal contact; win back before they leave",
    "At risk": "Win-back campaign; find out what changed",
    "Hibernating": "Low-cost reminder only; do not over-spend",
}
