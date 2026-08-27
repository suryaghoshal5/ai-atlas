"""Readable labels for NCO-2015 3-digit minor groups.

Single source of truth for chart annotations and paper tables so the same
occupation never appears under two names in two exhibits. GROUP_NAMES is the
set used by the white-collar exhibits (unchanged); EXTRA_NAMES adds the
blue-collar and agrarian groups that only the typology table needs.
"""

from __future__ import annotations

GROUP_NAMES = {
    "251": "Software developers", "241": "Finance professionals",
    "431": "Numerical clerks", "263": "Social/religious professionals",
    "243": "Sales & PR professionals", "235": "Other teaching professionals",
    "242": "Administration professionals", "264": "Authors & journalists",
    "411": "General office clerks", "331": "Financial associate professionals",
    "334": "Secretaries (admin)", "341": "Legal/social associates",
    "233": "Secondary teachers", "234": "Primary teachers",
    "522": "Shop salespersons", "351": "ICT technicians",
    "252": "Database professionals", "212": "Statisticians & actuaries", "216": "Architects & designers",
    "122": "Sales & marketing managers",
}

EXTRA_NAMES = {
    "112": "Proprietors & CEOs", "121": "Business services managers",
    "132": "Production managers", "134": "Professional services managers",
    "214": "Engineering professionals", "221": "Medical doctors",
    "222": "Nursing professionals", "232": "Vocational teachers",
    "311": "Physical science technicians", "312": "Mining/production supervisors",
    "321": "Medical associates", "412": "Secretaries", "413": "Keyboard operators",
    "421": "Tellers & money collectors", "422": "Client information clerks",
    "441": "Other clerical support", "512": "Cooks", "513": "Waiters & bartenders",
    "514": "Hairdressers & beauticians", "515": "Building supervisors",
    "516": "Other personal services", "521": "Street vendors",
    "524": "Other sales workers", "531": "Child/teacher aides", "532": "Personal care",
    "541": "Protective services", "611": "Crop farmers", "612": "Animal producers",
    "613": "Mixed crop & animal", "621": "Forestry workers", "711": "Building trades",
    "712": "Building finishers", "721": "Sheet & metal workers",
    "723": "Machinery mechanics", "731": "Handicraft workers", "732": "Printing trades",
    "741": "Electrical trades", "751": "Food processing trades",
    "752": "Wood treaters & joiners", "753": "Garment trades", "811": "Mining plant operators",
    "812": "Metal processing operators", "814": "Rubber & plastic operators",
    "815": "Textile machine operators", "817": "Wood processing operators",
    "821": "Assemblers", "831": "Locomotive operators", "832": "Car & van drivers",
    "833": "Truck & bus drivers", "834": "Mobile plant operators",
    "911": "Domestic cleaners", "921": "Farm labourers", "931": "Manual helpers",
    "932": "Manufacturing labourers", "933": "Transport labourers",
    "941": "Food preparation assistants", "951": "Street service workers",
    "961": "Refuse workers", "962": "Other elementary workers",
}

NAMES = {**GROUP_NAMES, **EXTRA_NAMES}


def label(group3: str) -> str:
    """Readable name for a 3-digit group, falling back to the bare code."""
    return NAMES.get(group3, f"NCO {group3}")
