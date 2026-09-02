"""E2-weight sensitivity of the headline atlas numbers (PRELIMINARY per D6).

Recomputes the four headline statistics under score_w = alpha + w*(zeta-alpha)
for w in {0, 0.5, 1}, plus top-10 group stability. Feeds the research-sample
appendix "Sensitivity To The E2 Weight".

Output: outputs/tables/e2_weight_sensitivity_PRELIMINARY.csv
"""

from __future__ import annotations

import polars as pl

from atlas_common import outputs_dir, processed_dir

WEIGHTS = [0.0, 0.5, 1.0]


def main() -> None:
    df = (pl.read_parquet(processed_dir() / "plfs_exposure_PRELIMINARY.parquet")
          .filter(pl.col("beta").is_not_null()))
    earn = df.filter(pl.col("monthly_earnings") > 0)
    W = float(df["weight"].sum())
    wb_tot = float((earn["monthly_earnings"] * earn["weight"]).sum())

    rows = []
    for w in WEIGHTS:
        s = pl.col("alpha") + w * (pl.col("zeta") - pl.col("alpha"))
        d = df.with_columns(s.alias("sc"))
        e = earn.with_columns(s.alias("sc"))
        hi = d.filter(pl.col("sc") >= 0.5)
        hi_e = e.filter(pl.col("sc") >= 0.5)
        rows.append({
            "e2_weight": w,
            "mean_emp_weighted": round(float((d["sc"] * d["weight"]).sum() / W), 3),
            "mean_wagebill_weighted": round(
                float((e["sc"] * e["monthly_earnings"] * e["weight"]).sum() / wb_tot), 3),
            "hi_worker_share_pct": round(float(hi["weight"].sum()) / W * 100, 1),
            "hi_earnings_share_pct": round(
                float((hi_e["monthly_earnings"] * hi_e["weight"]).sum()) / wb_tot * 100, 1),
        })

    g = (pl.read_parquet(processed_dir() / "group3_index_PRELIMINARY.parquet")
         .filter(pl.col("n_tasks") >= 5))
    tops = {}
    for w in WEIGHTS:
        gg = g.with_columns((pl.col("alpha") + w * (pl.col("zeta") - pl.col("alpha")))
                            .alias("sc")).sort("sc", descending=True)
        tops[w] = gg["group3"].head(10).to_list()
    overlap = len(set(tops[0.0]) & set(tops[1.0]))

    out = pl.DataFrame(rows)
    out.write_csv(outputs_dir() / "tables" / "e2_weight_sensitivity_PRELIMINARY.csv")
    print(out)
    print(f"top-10 overlap w=0 vs w=1: {overlap}/10")
    print("w=1-only entrants:", sorted(set(tops[1.0]) - set(tops[0.0])))


if __name__ == "__main__":
    main()
