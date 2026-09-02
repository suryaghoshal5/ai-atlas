"""Exhibit 4.7: India-native exposure vs O*NET-crosswalked exposure
(PRELIMINARY per D6).

Central methodological claim of the paper made quantitative: score the same
122 NCO-2015 3-digit groups two ways and measure the divergence.

  Native:      our beta from NCO-2015 task text (group3_index_PRELIMINARY).
  Crosswalked: Eloundou et al. (2024) occupation-level beta (GPT-4 'dv'
               ratings) on O*NET-SOC, mapped O*NET-SOC -> SOC-2010 ->
               ISCO-08 unit -> ISCO-08 minor group. NCO-2015 3-digit groups
               are ISCO-08 minor groups by construction.

Within a minor group the crosswalked score is the unweighted mean over all
mapped SOC occupations (no US employment weights folded in; noted as a
limitation). Divergence stats are reported unweighted and PLFS-employment
weighted.

Outputs:
  data/processed/crosswalk_comparison_PRELIMINARY.parquet
  outputs/tables/crosswalk_divergence_PRELIMINARY.csv (top gaps both ways)
  printed summary block (for the exhibit caption)
"""

from __future__ import annotations

import polars as pl

from atlas_common import outputs_dir, processed_dir, raw_dir


def load_crosswalked_beta() -> pl.DataFrame:
    import pandas as pd

    el = pl.read_csv(raw_dir() / "crosswalk" / "eloundou_occ_level.csv")
    # Eloundou scores are on the O*NET-SOC 2019 taxonomy (SOC-2018 based);
    # bridge back to O*NET-SOC 2010 first, else post-2010 code changes
    # (notably software, 15-113x -> 15-125x) silently drop out.
    bridge = pl.from_pandas(pd.read_excel(
        raw_dir() / "crosswalk" / "onetsoc_2010_to_2019.xlsx", skiprows=3))
    el = (el.join(bridge.select(pl.col("O*NET-SOC 2019 Code").alias("O*NET-SOC Code"),
                                pl.col("O*NET-SOC 2010 Code").alias("code10")),
                  on="O*NET-SOC Code", how="left")
          .with_columns(pl.coalesce(pl.col("code10"), pl.col("O*NET-SOC Code")).alias("code10")))
    el = el.with_columns(
        pl.col("code10").str.slice(0, 7).str.replace("-", "").cast(pl.Int64).alias("soc10"),
    ).group_by("soc10").agg(
        pl.col("dv_rating_beta").mean().alias("el_beta_gpt4"),
        pl.col("human_rating_beta").mean().alias("el_beta_human"),
    )
    cw = pl.from_pandas(pd.read_stata(raw_dir() / "crosswalk" / "soc10_isco08.dta"))
    cw = cw.with_columns(
        pl.col("soc10").cast(pl.Int64),
        pl.col("isco08").cast(pl.Int64).map_elements(lambda x: f"{x:04d}"[:3],
                                                     return_dtype=pl.Utf8).alias("group3"),
    )
    merged = cw.join(el, on="soc10", how="inner")
    return merged.group_by("group3").agg(
        pl.col("el_beta_gpt4").mean().alias("beta_crosswalked"),
        pl.col("el_beta_human").mean().alias("beta_crosswalked_human"),
        pl.len().alias("n_soc_mapped"),
    )


def main() -> None:
    native = (pl.read_parquet(processed_dir() / "group3_index_PRELIMINARY.parquet")
              .select("group3", pl.col("beta").alias("beta_native"), "n_tasks"))
    emp = (pl.read_parquet(processed_dir() / "plfs_exposure_PRELIMINARY.parquet")
           .filter(pl.col("beta").is_not_null())
           .group_by("group3").agg((pl.col("weight").sum() / 1e6).alias("workers_m")))
    cwb = load_crosswalked_beta()

    df = (native.join(cwb, on="group3", how="inner")
          .join(emp, on="group3", how="left")
          .with_columns((pl.col("beta_native") - pl.col("beta_crosswalked")).alias("gap"))
          .sort("gap"))
    df.write_parquet(processed_dir() / "crosswalk_comparison_PRELIMINARY.parquet")

    w = pl.col("workers_m").fill_null(0)
    n = df.height
    corr = float(pl.DataFrame(df).select(pl.corr("beta_native", "beta_crosswalked")).item())
    tot_w = float(df.select(w.sum()).item())
    wmean = lambda c: float(df.select((pl.col(c) * w).sum() / tot_w).item())
    mean_abs_gap = float(df["gap"].abs().mean())
    wmean_abs_gap = float(df.select((pl.col("gap").abs() * w).sum() / tot_w).item())
    big = int((df["gap"].abs() >= 0.10).sum())
    big_w = float(df.filter(pl.col("gap").abs() >= 0.10).select(w.sum()).item())

    print(f"matched groups: {n}/122 (unmatched: "
          f"{sorted(set(native['group3']) - set(df['group3']))})")
    print(f"correlation native vs crosswalked: {corr:.2f}")
    print(f"mean native beta {float(df['beta_native'].mean()):.3f} vs crosswalked {float(df['beta_crosswalked'].mean()):.3f}")
    print(f"employment-weighted: native {wmean('beta_native'):.3f} vs crosswalked {wmean('beta_crosswalked'):.3f}")
    print(f"mean |gap|: {mean_abs_gap:.3f} unweighted, {wmean_abs_gap:.3f} employment-weighted")
    print(f"groups with |gap| >= 0.10: {big}/{n}, holding {big_w:.0f}M workers ({big_w/tot_w*100:.0f}%)")

    top = pl.concat([df.head(8), df.tail(8)]).select(
        "group3", "beta_native", "beta_crosswalked", "gap", "workers_m", "n_soc_mapped", "n_tasks")
    top.write_csv(outputs_dir() / "tables" / "crosswalk_divergence_PRELIMINARY.csv")
    with pl.Config(tbl_rows=20):
        print(top)


if __name__ == "__main__":
    main()
