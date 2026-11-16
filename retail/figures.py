"""Static charts for the README. The interactive version is the Tableau Public dashboard."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE = "#2a78d6"     # categorical slot 1
ORANGE = "#eb6834"   # categorical slot 2
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 10,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": INK_2,
    "axes.titlecolor": INK,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "xtick.color": MUTED,
    "ytick.color": INK_2,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "savefig.dpi": 160,
    "savefig.bbox": "tight",
})


def _hgrid(ax):
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)


def customers_vs_revenue(summary: pd.DataFrame, path):
    seg = summary["segment"][::-1]
    y = np.arange(len(seg))
    h = 0.38
    fig, ax = plt.subplots(figsize=(8, 5.2))
    ax.barh(y + h / 2 + 0.01, summary["share_of_customers_pct"][::-1], h, color=BLUE,
            label="Share of customers")
    ax.barh(y - h / 2 - 0.01, summary["share_of_revenue_pct"][::-1], h, color=ORANGE,
            label="Share of revenue")
    for yi, c, r in zip(y, summary["share_of_customers_pct"][::-1], summary["share_of_revenue_pct"][::-1]):
        ax.text(c + 0.6, yi + h / 2, f"{c:.0f}%", va="center", fontsize=8.5, color=INK_2)
        ax.text(r + 0.6, yi - h / 2, f"{r:.0f}%", va="center", fontsize=8.5, color=INK_2)
    ax.set_yticks(y, seg)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    _hgrid(ax)
    ax.legend(frameon=False, loc="lower right", labelcolor=INK_2)
    ax.set_title("Who the revenue comes from")
    fig.savefig(path)
    plt.close(fig)


def holdout_repeat_rate(validation: pd.DataFrame, path):
    v = validation[validation["segment"] != "All customers"].iloc[::-1]
    overall = validation.loc[validation["segment"] == "All customers", "bought_again_pct"].iat[0]
    y = np.arange(len(v))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(y, v["bought_again_pct"], 0.6, color=BLUE)
    for yi, val in zip(y, v["bought_again_pct"]):
        ax.text(val + 1, yi, f"{val:.0f}%", va="center", fontsize=8.5, color=INK_2)
    ax.axvline(overall, color=INK_2, linewidth=1, linestyle=(0, (3, 3)))
    ax.text(overall + 1, -0.75, f"All customers: {overall:.0f}%", fontsize=8.5, color=INK_2)
    ax.set_ylim(-1, len(v) - 0.4)
    ax.set_yticks(y, v["segment"])
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    _hgrid(ax)
    ax.set_title("Share of each segment that ordered again in the next 6 months")
    fig.savefig(path)
    plt.close(fig)


def cohort_heatmap(cohorts: pd.DataFrame, path, first="2010-01-01", last="2010-12-01", months=12):
    c = cohorts[(cohorts["cohort"] >= first) & (cohorts["cohort"] <= last)
                & (cohorts["months_since_first"].between(1, months))]
    # Dec 2011 holds only 9 days of data, so it would understate retention: leave it blank.
    month_index = c["cohort"].dt.year * 12 + c["cohort"].dt.month - 1 + c["months_since_first"]
    c = c[month_index < 2011 * 12 + 11]
    grid = c.pivot(index="cohort", columns="months_since_first", values="retention_pct")
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue", BLUE_RAMP)
    fig, ax = plt.subplots(figsize=(9, 5))
    im = ax.imshow(grid.values, cmap=cmap, aspect="auto", vmin=0, vmax=np.nanmax(grid.values))
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            val = grid.values[i, j]
            if np.isnan(val):
                continue
            ax.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=8,
                    color="#ffffff" if val > 0.55 * np.nanmax(grid.values) else INK)
    ax.set_xticks(range(grid.shape[1]), grid.columns)
    ax.set_yticks(range(grid.shape[0]), [d.strftime("%b %Y") for d in grid.index])
    ax.set_xlabel("Months after first order")
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, format=mtick.PercentFormatter(decimals=0))
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=MUTED, length=0)
    ax.set_title("Customer retention by first-order month, 2010 cohorts (% ordering again)")
    fig.savefig(path)
    plt.close(fig)


def monthly_revenue(monthly: pd.DataFrame, path):
    m = monthly.groupby("month")["revenue_gbp"].sum() / 1000
    m = m[m.index < m.index.max()]  # final month is partial (data ends 9 Dec 2011)
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(m.index, m.values, color=BLUE, linewidth=2)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, colors=MUTED)
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("£{x:,.0f}k"))
    peak = m.idxmax()
    ax.annotate(f"£{m.max():,.0f}k", (peak, m.max()), xytext=(0, 6), textcoords="offset points",
                ha="center", fontsize=8.5, color=INK_2)
    ax.set_ylim(0, m.max() * 1.15)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.set_title("Monthly revenue, Dec 2009 to Nov 2011 (strong Q4 peak each year)")
    fig.savefig(path)
    plt.close(fig)
