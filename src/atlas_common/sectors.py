"""NAS activity heads: GVA levels and their NIC-2008 divisions.

Single source for every sector-level exhibit so the GVA chart, the sector
master and anything later all cut India the same way.

GVA at basic prices, CURRENT prices, FY2023-24 First Revised Estimates —
Statement 4A, MoSPI Press Note on SAE 2024-25 (28 Feb 2025), archived at
data/raw/nas/mospi_sae_2024-25_fre_2023-24.pdf (manifested). Rs crore.

NAS seams handled explicitly: computer & information services (NIC 62-63) sit
in "Financial, Real Estate & Professional Services"; telecom & broadcasting
(58-61) in the trade/transport/communication group. The division sets are
disjoint, so every worker lands in at most one head.
"""

from __future__ import annotations

# (label, GVA Rs crore 2023-24 FRE, NIC-2008 divisions)
NAS = [
    ("Agriculture & allied",              4877867, list(range(1, 4))),
    ("Mining & quarrying",                 532343, list(range(5, 10))),
    ("Manufacturing",                     3921596, list(range(10, 34))),
    ("Utilities",                          766435, list(range(35, 40))),
    ("Construction",                      2401618, list(range(41, 44))),
    ("Trade, hotels, transport, comms",   4828505, [*range(45, 48), *range(49, 54), 55, 56, *range(58, 62)]),
    ("Financial, real estate, prof. svcs", 6244153, [62, 63, *range(64, 69), *range(69, 76), *range(77, 83)]),
    ("Public admin, defence, other svcs", 3840370, [84, 85, *range(86, 89), *range(90, 100)]),
]
GVA_TOTAL = 27412888  # Rs crore, Statement 4A

NAS_DIVISIONS = {label: divs for label, _, divs in NAS}
NAS_GVA_CRORE = {label: gva for label, gva, _ in NAS}
