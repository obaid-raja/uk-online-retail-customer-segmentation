import itertools

import pandas as pd
import pytest

from retail import config
from retail.clean import clean
from retail.rfm import band, cohort_retention, rfm_table, score, segment_of


def _raw():
    return pd.DataFrame({
        "invoice": ["1001", "1001", "C1002", "1003", "1004", "1005", "1006", "1006"],
        "stock_code": ["85123A", "85123A", "85123A", "POST", "22423", "22423", "21232", "M"],
        "description": ["x"] * 8,
        "quantity": [6, 6, -6, 1, 2, 0, 3, 1],
        "invoice_date": pd.to_datetime(["2011-01-01"] * 8),
        "price": [2.55, 2.55, 2.55, 18.0, 12.75, 1.0, 1.25, 5.0],
        "customer_id": [1.0, 1.0, 1.0, 2.0, None, 3.0, 3.0, 3.0],
        "country": ["United Kingdom"] * 8,
    })


def test_clean_removes_each_bad_row_type():
    tx, log = clean(_raw())
    # Kept: invoice 1001 once (duplicate dropped) and 1006 / 21232.
    assert sorted(tx["invoice"]) == ["1001", "1006"]
    assert not tx["invoice"].str.startswith("C").any()
    assert tx["stock_code"].str.match(config.PRODUCT_CODE_PATTERN).all()
    assert (tx["quantity"] > 0).all() and (tx["price"] > 0).all()
    assert log["rows_removed"].sum() == len(_raw()) - len(tx)
    assert tx.loc[tx["invoice"] == "1001", "revenue"].iat[0] == pytest.approx(15.30)


def test_rfm_table_values():
    tx = pd.DataFrame({
        "customer_id": [1, 1, 2],
        "invoice": ["a", "b", "c"],
        "invoice_date": pd.to_datetime(["2011-01-01 10:00", "2011-01-20 15:00", "2011-01-05 09:00"]),
        "revenue": [10.0, 30.0, 5.0],
        "country": ["UK", "UK", "France"],
    })
    r = rfm_table(tx, pd.Timestamp("2011-01-31")).set_index("customer_id")
    assert r.loc[1, "recency_days"] == 11
    assert r.loc[1, "frequency"] == 2
    assert r.loc[1, "monetary"] == 40.0
    assert r.loc[2, "recency_days"] == 26


def test_bands_are_equal_sized_and_ordered():
    s = pd.Series([1] * 60 + list(range(2, 42)))  # many ties, like one-order customers
    b = band(s)
    assert b.value_counts().tolist() == [20] * 5
    assert b.iloc[-1] == 5  # highest value -> best band
    assert band(pd.Series(range(100)), higher_is_better=False).iloc[0] == 5  # lowest recency -> best


def test_every_rf_code_has_exactly_one_segment():
    import re
    for r, f in itertools.product(range(1, 6), repeat=2):
        code = f"{r}{f}"
        hits = [p for p in config.SEGMENT_MAP if re.fullmatch(p, code)]
        assert len(hits) == 1, code
        assert segment_of(code) in config.SEGMENT_ORDER


def test_score_assigns_champions_to_recent_frequent_big_spenders():
    rfm = pd.DataFrame({
        "customer_id": range(10),
        "recency_days": range(10),          # customer 0 bought most recently
        "frequency": range(10, 0, -1),      # and most often
        "monetary": range(1000, 0, -100),   # and spent most
        "avg_order_value": [1.0] * 10,
    })
    s = score(rfm).set_index("customer_id")
    assert s.loc[0, "rfm_code"] == "555"
    assert s.loc[0, "segment"] == "Champions"
    assert s.loc[9, "segment"] == "Hibernating"


def test_cohort_month_zero_is_full_cohort():
    tx = pd.DataFrame({
        "customer_id": [1, 1, 2, 3],
        "invoice_date": pd.to_datetime(["2010-01-05", "2010-03-02", "2010-01-20", "2010-02-01"]),
    })
    c = cohort_retention(tx)
    jan = c[c["cohort"] == "2010-01-01"].set_index("months_since_first")
    assert jan.loc[0, "retention_pct"] == 100
    assert jan.loc[2, "retention_pct"] == 50
