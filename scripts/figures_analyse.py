"""Analyze phase - charts built from the aggregated CSV files (no database access).

Usage: python -I scripts/figures_analyse.py [--csv-dir results/analysis] [--out-dir visualizations]
English edition of the original chart script: same data, same calculations, same colors;
only titles, labels and number formatting are translated.
Colors: blue = annual members, orange = casual riders, identical in every chart; direct labels
and a legend so that identity never relies on color alone.
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = {"member": "#2a78d6", "casual": "#eb6834"}
LAB = {"member": "Annual members", "casual": "Casual riders"}
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
DAYS = {1: "Sun", 2: "Mon", 3: "Tue", 4: "Wed", 5: "Thu", 6: "Fri", 7: "Sat"}
DAY_ORDER = [2, 3, 4, 5, 6, 7, 1]
SOURCE = "Source: Divvy/Cyclistic, rides from 1 Oct 2025 to 30 Sep 2026, cleaning rules v3.2 (6,012,458 rides)"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 11, "axes.titlesize": 14, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y",
    "grid.color": GRID, "grid.linewidth": 0.8, "lines.linewidth": 2, "legend.frameon": False,
})


def en(x, dec=0):
    """English number format; exact decimal rounding (ROUND_HALF_UP) to avoid binary errors (74.05 -> 74.1)."""
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(str(x)).quantize(Decimal(1).scaleb(-dec), rounding=ROUND_HALF_UP)
    return f"{q:,.{dec}f}"


def finish(fig, ax, title, subtitle, path, legend=True):
    ax.set_title(title, loc="left", pad=28)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, color=INK2, fontsize=10, va="bottom")
    if legend:
        ax.legend(loc=legend if isinstance(legend, str) else "upper right")
    fig.text(0.01, 0.01, SOURCE, color=INK2, fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def grouped(ax, cats, series, fmt_label=None, width=0.38):
    """Grouped bars, members / casual riders (2 px gap via a surface-colored edge)."""
    xs = range(len(cats))
    for i, mc in enumerate(("member", "casual")):
        vals = series[mc]
        pos = [x + (i - 0.5) * width for x in xs]
        bars = ax.bar(pos, vals, width, color=C[mc], label=LAB[mc], edgecolor=SURFACE, linewidth=1.5)
        if fmt_label:
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, b.get_height(), fmt_label(v), ha="center", va="bottom",
                        fontsize=8.5, color=INK2)
    ax.set_xticks(list(xs))
    ax.set_xticklabels(cats)
    ax.set_ylim(0, max(max(series["member"]), max(series["casual"])) * 1.22)  # room for labels and legend


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv-dir", default=os.path.join(ROOT, "results", "analysis"))
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "visualizations"))
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    rd = lambda n: pd.read_csv(os.path.join(a.csv_dir, f"{n}.csv"))  # noqa: E731
    out = lambda n: os.path.join(a.out_dir, n)  # noqa: E731

    # F1 - ride volume
    u = rd("a01_usagers").set_index("member_casual")
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for i, mc in enumerate(("member", "casual")):
        ax.barh(i, u.loc[mc, "trajets"], color=C[mc], height=0.55)
        ax.text(u.loc[mc, "trajets"], i, f"  {en(u.loc[mc, 'trajets'])} rides ({en(u.loc[mc, 'part_pct'], 1)}%)",
                va="center", color=INK, fontsize=11)
    ax.set_yticks([0, 1])
    ax.set_yticklabels([LAB["member"], LAB["casual"]])
    ax.invert_yaxis()
    ax.set_xlim(0, u["trajets"].drop("TOUS").max() * 1.45)
    ax.grid(False)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    finish(fig, ax, "Nearly 2 out of 3 rides are taken by members",
           "Number of rides (not people: the data contain no rider identifier)", out("f1_ride_volume.png"), legend=False)

    # F2 - duration distribution
    d = rd("a02_durees_tranches")
    cats = [t.split(": ")[1] for t in sorted(d["tranche"].unique())]
    s = {mc: d[d.member_casual == mc].sort_values("tranche")["part_pct"].tolist() for mc in ("member", "casual")}
    fig, ax = plt.subplots(figsize=(11, 5))
    grouped(ax, cats, s, lambda v: "<0.1" if v < 0.1 else f"{en(v, 1)}")
    ax.set_ylabel("% of the group's rides")
    finish(fig, ax, "13.5% of casual rides last over 30 min, vs 5.4% of member rides",
           f"Distribution of ride durations - median: members {en(u.loc['member', 'mediane_min'], 1)} min, "
           f"casual riders {en(u.loc['casual', 'mediane_min'], 1)} min", out("f2_duration_distribution.png"))

    # F3 - day of the week (share of the group's rides)
    j = rd("a03_jour")
    s = {mc: [float(j[(j.member_casual == mc) & (j.day_of_week == k)]["part_pct"].iloc[0]) for k in DAY_ORDER]
         for mc in ("member", "casual")}
    fig, ax = plt.subplots(figsize=(10, 4.8))
    grouped(ax, [DAYS[k] for k in DAY_ORDER], s, lambda v: f"{en(v, 1)}")
    ax.set_ylabel("% of the group's rides")
    finish(fig, ax, "Weekends account for 37% of casual rides, vs 23% for members",
           "Share of each group's rides by day of departure", out("f3_day_of_week.png"), legend="upper left")

    # F3b - median duration by day
    s = {mc: [float(j[(j.member_casual == mc) & (j.day_of_week == k)]["mediane_min"].iloc[0]) for k in DAY_ORDER]
         for mc in ("member", "casual")}
    fig, ax = plt.subplots(figsize=(10, 4.8))
    grouped(ax, [DAYS[k] for k in DAY_ORDER], s, lambda v: f"{en(v, 2)}")
    ax.set_ylabel("Median duration (min)")
    finish(fig, ax, "The duration gap widens at weekends", "Median ride duration by day of departure",
           out("f3b_median_duration_by_day.png"), legend="upper left")

    # F4 - monthly trend (volume)
    m = rd("a04_mois")
    months = sorted(m["mois"].unique())
    fig, ax = plt.subplots(figsize=(11, 4.8))
    for mc in ("member", "casual"):
        v = [int(m[(m.mois == mo) & (m.member_casual == mc)]["trajets"].iloc[0]) for mo in months]
        ax.plot(months, v, color=C[mc], label=LAB[mc], marker="o", markersize=5)
        ax.text(months[-1], v[-1], f"  {LAB[mc]}", color=INK2, va="center", fontsize=9)
    ax.set_ylabel("Rides per month")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: en(x)))
    ax.tick_params(axis="x", rotation=45)
    finish(fig, ax, "Seasonality: ×14 between January and July for casual riders, ×4.7 for members",
           "Number of rides by month of departure (Oct 2025 - Sep 2026)", out("f4_monthly_trend.png"), legend="lower right")

    # F4b - casual share by month (separate chart: no dual axis)
    v = [float(m[(m.mois == mo) & (m.member_casual == "casual")]["part_du_mois_pct"].iloc[0]) for mo in months]
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(months, v, color=C["casual"], marker="o", markersize=5, label=LAB["casual"])
    for x_, y_ in zip(months, v):
        ax.text(x_, y_ + 0.8, f"{en(y_, 0)}%", ha="center", fontsize=8.5, color=INK2)
    ax.set_ylabel("% of the month's rides")
    ax.set_ylim(0, max(v) * 1.2)
    ax.tick_params(axis="x", rotation=45)
    finish(fig, ax, "The casual share peaks in summer", "Share of rides taken by casual riders, by month",
           out("f4b_casual_share_by_month.png"), legend=False)

    # F5 - hourly profile, weekdays / weekend (small multiples, same scale)
    h = rd("a05_heure")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    for ax, tj, title in zip(axes, ("semaine", "week-end"), ("Weekdays", "Weekend")):
        for mc in ("member", "casual"):
            sub = h[(h.member_casual == mc) & (h.type_jour == tj)].sort_values("heure")
            ax.plot(sub["heure"], sub["part_pct"], color=C[mc], label=LAB[mc])
        ax.set_title(title, loc="left", fontsize=12)
        ax.set_xticks(range(0, 24, 3))
        ax.set_xlabel("Hour of departure")
    axes[0].set_ylabel("% of the group's rides (this type of day)")
    axes[1].legend(loc="upper left")
    fig.suptitle("On weekdays, the morning peak (7-9 a.m.) is twice as pronounced among members;\n"
                 "at weekends, the hourly profiles are similar", x=0.01, ha="left",
                 fontweight="bold", fontsize=14)
    fig.text(0.01, 0.01, SOURCE, color=INK2, fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 0.90))
    fig.savefig(out("f5_hourly_profile.png"), dpi=150)
    plt.close(fig)

    # F6 - bike type
    v = rd("a06_velo")
    types = ["classic_bike", "electric_bike"]
    s = {mc: [100 * int(v[(v.member_casual == mc) & (v.rideable_type == t)]["trajets"].iloc[0])
              / int(v[v.member_casual == mc]["trajets"].sum()) for t in types]
         for mc in ("member", "casual")}
    fig, ax = plt.subplots(figsize=(8, 4.6))
    grouped(ax, ["Classic bike", "E-bike"], s, lambda x: f"{en(x, 1)}%")
    ax.set_ylabel("% of the group's rides")
    finish(fig, ax, "E-bikes dominate in both groups",
           "Share of rides by bike type (the excluded rides < 60 s were all e-bike rides)", out("f6_bike_type.png"),
           legend="upper left")

    # F7 - interaction: median duration by bike type and type of day
    it = rd("a07_interactions")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    for ax, tj, title in zip(axes, ("semaine", "week-end"), ("Weekdays", "Weekend")):
        s = {mc: [float(it[(it.member_casual == mc) & (it.rideable_type == t) & (it.type_jour == tj)]["mediane_min"].iloc[0])
                  for t in types] for mc in ("member", "casual")}
        grouped(ax, ["Classic", "Electric"], s, lambda x: f"{en(x, 2)}")
        ax.set_title(title, loc="left", fontsize=12)
    axes[0].set_ylabel("Median duration (min)")
    axes[0].legend(loc="upper right")
    fig.suptitle("The longest rides: casual riders, classic bikes, weekends", x=0.01, ha="left",
                 fontweight="bold", fontsize=14)
    fig.text(0.01, 0.01, SOURCE, color=INK2, fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(out("f7_bike_type_by_day_type.png"), dpi=150)
    plt.close(fig)

    # F8 - round trips
    b = rd("a08_boucles").set_index("member_casual")
    fig, ax = plt.subplots(figsize=(11, 3.8))
    for i, mc in enumerate(("member", "casual")):
        ax.barh(i, b.loc[mc, "part_boucle_pct"], color=C[mc], height=0.55)
        ax.text(b.loc[mc, "part_boucle_pct"], i, f"  {en(b.loc[mc, 'part_boucle_pct'], 1)}%", va="center")
    ax.set_yticks([0, 1])
    ax.set_yticklabels([LAB["member"], LAB["casual"]])
    ax.invert_yaxis()
    ax.set_xlim(0, b["part_boucle_pct"].max() * 1.4)
    ax.grid(False)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    finish(fig, ax, "Round trips: 7.4% of casual rides, 2.2% of member rides",
           "End station = start station, among rides with both stations (66% of casual rides, 68% of member rides)",
           out("f8_round_trips.png"), legend=False)

    # F9 - daily series, 7-day rolling mean
    dj = rd("a10_jours")
    dj["date"] = pd.to_datetime(dj["date"])
    fig, ax = plt.subplots(figsize=(12, 4.6))
    for mc in ("member", "casual"):
        sr = dj[dj.member_casual == mc].set_index("date")["trajets"].asfreq("D", fill_value=0)
        ax.plot(sr.index, sr.rolling(7, center=True).mean(), color=C[mc], label=LAB[mc])
    ax.set_ylabel("Rides per day (7-day rolling mean)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: en(x)))
    finish(fig, ax, "Same seasonal calendar, much stronger amplitude for casual riders",
           "Rides by day of departure, centered 7-day rolling mean", out("f9_daily_series.png"), legend="upper center")
    print(f"Charts written to {a.out_dir}")


if __name__ == "__main__":
    main()
