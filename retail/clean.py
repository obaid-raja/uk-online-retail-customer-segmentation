"""Load the raw UCI Online Retail II workbook and clean it into a transactions table."""
import pandas as pd

from . import config

RAW_COLUMNS = {
    "Invoice": "invoice",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "Price": "price",
    "Customer ID": "customer_id",
    "Country": "country",
}


def load_raw(use_cache: bool = True) -> pd.DataFrame:
    """Both sheets of the workbook as one table. Reading the .xlsx is slow, so the
    first read is cached as a compressed CSV."""
    if use_cache and config.RAW_CACHE.exists():
        df = pd.read_csv(config.RAW_CACHE, dtype={"invoice": str, "stock_code": str},
                         parse_dates=["invoice_date"])
        return df
    sheets = pd.read_excel(config.RAW_XLSX, sheet_name=None,
                           dtype={"Invoice": str, "StockCode": str})
    df = pd.concat(sheets.values(), ignore_index=True).rename(columns=RAW_COLUMNS)
    config.RAW_CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.RAW_CACHE, index=False, compression="gzip")
    return df


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (clean transactions, cleaning log). Each step is logged with the rows it removed."""
    df = raw.copy()
    df["invoice"] = df["invoice"].astype(str).str.strip()
    df["stock_code"] = df["stock_code"].astype(str).str.strip().str.upper()
    log = [("Raw rows (both sheets)", len(df), 0)]

    def step(name, keep_mask):
        nonlocal df
        before = len(df)
        df = df[keep_mask(df)]
        log.append((name, len(df), before - len(df)))

    step("Remove exact duplicate rows", lambda d: ~d.duplicated())
    step("Remove rows with no customer ID", lambda d: d["customer_id"].notna())
    step("Remove cancellations (invoice starts with C)", lambda d: ~d["invoice"].str.startswith("C"))
    step("Remove non-product codes (postage, fees, adjustments)",
         lambda d: d["stock_code"].str.match(config.PRODUCT_CODE_PATTERN))
    step("Remove zero or negative quantity or price",
         lambda d: (d["quantity"] > 0) & (d["price"] > 0))

    df = df.assign(
        customer_id=df["customer_id"].astype(int),
        revenue=df["quantity"] * df["price"],
    ).reset_index(drop=True)
    log_df = pd.DataFrame(log, columns=["step", "rows_remaining", "rows_removed"])
    return df, log_df
