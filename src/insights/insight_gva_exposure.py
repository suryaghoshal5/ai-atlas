"""GVA-weighted exposure exhibit: where India's value-add meets AI exposure.

NAS GVA at basic prices, CURRENT prices, FY2023-24 First Revised Estimates —
Statement 4A, MoSPI Press Note on SAE 2024-25 (28 Feb 2025), archived at
data/raw/nas/mospi_sae_2024-25_fre_2023-24.pdf (manifested). Rs crore.

Exposure per NAS activity = employment-weighted mean worker exposure of PLFS
workers in the activity's NIC-2008 divisions. NAS seam handled explicitly:
computer & information services (NIC 62-63) sit in "Financial, Real Estate &
Professional Services"; telecom & broadcasting (58-61) in the trade/transport/
communication group. PRELIMINARY per D6.
"""

from __future__ import annotations

from datetime import date

import matplotlib.pyplot as plt
import polars as pl

from atlas_common import outputs_dir, processed_dir
from atlas_common.sectors import GVA_TOTAL, NAS
from insights._style import (SB_GOLD, SB_GREY, SB_RED, add_source, apply_style,
                             head_sub)

OUT = outputs_dir() / "substack"
DATASET = ("PLFS 2023-24 x NCO-2015 exposure index (preliminary LLM scoring); "
           "GVA: NAS Statement 4A, FY2023-24 FRE, current prices (MoSPI)")



def main() -> None:
    apply_style()
    OUT.mkdir(parents=True, exist_ok=True)
    df = (pl.read_parquet(processed_dir() / "plfs_exposure_PRELIMINARY.parquet")
          .filter(pl.col("beta").is_not_null())
          .with_columns(pl.col("nic5").cast(pl.Utf8).str.zfill(5).str.slice(0, 2)
                        .cast(pl.Int32, strict=False).alias("nic2")))
    nat = float((df["beta"] * df["weight"]).sum() / df["weight"].sum())

    rows = []
    for label, gva, divs in NAS:
        s = df.filter(pl.col("nic2").is_in(divs))
        w = float(s["weight"].sum())
        rows.append({"label": label, "gva_kcr": gva / 1e5,  # Rs lakh crore
                     "gva_share": gva / GVA_TOTAL,
                     "E": float((s["beta"] * s["weight"]).sum() / w) if w else None,
                     "workers_m": w / 1e6})
    t = pl.DataFrame(rows).sort("E")
    gva_weighted_E = float(sum(r["gva_share"] * r["E"] for r in rows))
    exposed_gva_share = float(sum(r["gva_share"] for r in rows if r["E"] > nat))

    fig, ax = plt.subplots(figsize=(7.2, 4.9))
    names, E = t["label"].to_list(), t["E"].to_list()
    shares = t["gva_share"].to_list()
    colors = [SB_RED if e > nat else SB_GREY for e in E]
    ypos = list(range(len(names)))
    ax.barh(ypos, E, color=colors, height=0.62)
    ax.axvline(nat, color=SB_GOLD, lw=1.4, ls="--")
    ax.text(nat + 0.006, 4.52, f"employment-weighted avg {nat:.2f}",
            fontsize=8, color="#a67102")
    for y, e, sh, g in zip(ypos, E, shares, t["gva_kcr"].to_list()):
        ax.text(e + 0.005, y, f"{e:.2f}   ({sh:.0%} of GVA, Rs{g:.0f}L cr)",
                va="center", fontsize=8, color=SB_RED if e > nat else SB_GREY,
                fontweight="bold")
    ax.set_yticks(ypos)
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlim(0, max(E) * 1.75)
    head_sub(ax, f"Above-average exposure industries produce {exposed_gva_share:.0%} of India's GVA\n"
                 f"Worker exposure by NAS activity; labels: share of FY2023-24 GVA at\n"
                 f"current prices (total Rs274L cr). GVA-weighted mean exposure "
                 f"{gva_weighted_E:.2f}\nvs employment-weighted {nat:.2f}. "
                 "PLFS 2023-24 + NAS Statement 4A.")
    ax.set_xlabel("Employment-weighted mean exposure score (0-1)")
    add_source(fig, DATASET)
    fig.savefig(OUT / "insight_gva_exposure.png", bbox_inches="tight")
    plt.close(fig)

    prov = OUT / "provenance.md"
    existing = prov.read_text() if prov.exists() else "# Substack chart provenance\n\n"
    existing += (f"### insight_gva_exposure ({date.today()})\n"
                 + "; ".join(f"{r['label']}: E={r['E']:.3f}, GVA share {r['gva_share']:.3f}"
                             for r in rows)
                 + f"; GVA-weighted mean E={gva_weighted_E:.4f}; "
                 f"share of GVA in above-avg-exposure activities={exposed_gva_share:.4f}"
                 f"\nSource: {DATASET}.\n")
    prov.write_text(existing)
    print(f"GVA-weighted mean E = {gva_weighted_E:.3f} | employment-weighted = {nat:.3f}")
    print(f"GVA share in above-average-exposure activities = {exposed_gva_share:.1%}")
    for r in sorted(rows, key=lambda r: -r["E"]):
        print(f"  {r['label']:38s} E={r['E']:.3f}  GVA {r['gva_share']:.1%}  ({r['workers_m']:.0f}M workers)")


if __name__ == "__main__":
    main()
