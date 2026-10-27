# data/

## `bea_direct_requirements.csv`

The published rates that make this challenge's supply edges a modeling choice rather than an
invention.

Each row says: **businesses in industry A buy this many cents of input from industry B, per
dollar of A's output.** Those numbers come from the Bureau of Economic Analysis Input-Output
Accounts, built from survey and tax data. They are measured, not estimated by us.

| Column | Meaning |
|---|---|
| `buyer_naics4` | The purchasing industry, 4-digit NAICS |
| `supplier_naics4` | The supplying industry, 4-digit NAICS |
| `coefficient` | Cents of input per dollar of buyer output |

**Read it.** You should not trust generated edges you cannot inspect, and neither should a judge.
Everything the supply-edge generator knows is in this file plus four constants at the top of
Section 7 of the notebook: a coefficient floor, a distance limit, a generic-supplier cutoff and a
cap on suppliers per buyer. There is no randomness and nothing hidden.

**Be clear about what it does and does not say.** It says restaurants buy from food wholesalers
at a measurable rate. It does **not** say that *this* restaurant buys from *that* wholesaler.
The notebook makes that assignment, using industry match plus walking distance, and that
assignment is ours. When judges check which half is real, that sentence is the answer.

Improving the allocation rule is one of the best add-ons available in this challenge. The rule we
ship is deliberately simple so that beating it is possible.

## `bea_naics_concordance.csv`

BEA uses its own industry codes, not NAICS. This is the mapping used to translate them, written
out alongside the coefficients so the translation is auditable rather than implied. BEA states
its summary level "generally corresponds to" 4-digit NAICS—note *generally*. The correspondence
is not perfectly one-to-one, and a few BEA industries have no NAICS analogue at all.

## Why these are committed rather than downloaded

BEA's API requires a free registration key. That is fine for one person and a bad idea for a room
of 150 people on event morning. We fetched it once and pinned the result.

`scripts/fetch_bea.py` is the generator. It discovers BEA's table id at runtime rather than
hardcoding one, because BEA does not publish a list of table ids—so if you regenerate, you get
whatever BEA calls Direct Requirements today rather than whatever it called it in 2023.

**License:** public domain. BEA states: *"Unless stated otherwise, the information posted on the
BEA web site is in the public domain and may be used or reproduced without specific permission."*
(https://bea.gov/help/faq/145)

## Everything else

The businesses, the loans, the job counts and the demographics are all pulled live by the
notebook. They are not in this folder, and `.gitignore` keeps stray CSVs out so the repo stays
cloneable on conference wifi.
