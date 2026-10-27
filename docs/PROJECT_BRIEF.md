# A4I 2026 Challenge 3: Community Economic Resilience & Micro-Grants — Project Brief

## 1. Core Problem to Solve

Traditional small-business relief ranks applicants in isolation by how distressed they are. That ignores what makes a commercial corridor a local economy: **businesses hold each other up**. When a supplier or anchor business closes, the damage cascades downstream to buyers, service providers, and lunch spots that were previously healthy.

**The Goal:** Given **one San Francisco commercial corridor** and a **fixed relief budget** (e.g., \$50,000), build an ADK agent backed by a **BigQuery Property Graph (GQL)** that traces multi-hop economic cascades and produces a **defended Grant Memo** arguing for funding based on what it protects downstream—not just a centrality score.

---

## 2. The Seven Questions the Agent Must Handle

A grant officer does not just ask "who is most connected?" Over a single afternoon, they ask:

1. **Downstream Damage:** *"If I fund nobody, which of these closures does the most damage?"* → Multi-hop graph traversal weighted by downstream exposure.
2. **Comparative Defense:** *"Show me why this one and not that one."* → Explicit paths, hop counts, and edge intensities comparing the top choice vs. the runner-up.
3. **Downstream Fragility:** *"This applicant has four suppliers/buyers downstream. Are any of them already fragile?"* → Graph traversal combined with SBA `borrowed_from` loan/charge-off records.
4. **Proactive Discovery:** *"Nobody at the far end of that chain applied. Should they have?"* → Identifying un-applied businesses exposed by the graph.
5. **Explicit Assumptions:** *"What does \$8,000 actually change?"* → Honest statement of what the data cannot prove and what probability change is assumed.
6. **Neighborhood Context:** *"Whose neighborhood does this help?"* → Joining ACS census tract demographics (`poverty_rate`, `no_vehicle_rate`, `assistance_rate`).
7. **Executive Output:** *"Write it up. I present Friday."* → Assembling the structured **Grant Memo**.

> **Anti-Goal Warning:** Do **not** build a centrality calculator that always funds the biggest hub. The biggest hub is often the most robust node in the network. Your agent must know when *not* to fund the biggest hub and when to refuse if data cannot distinguish two applicants.

---

## 3. Three Tracks (Same Architecture, Different Entry Point)

| Track | Situation | User | Graph Traversal Direction |
|---|---|---|---|
| **1. Main Street Relief** | Queue of applicants, scarce funds | City economic-development officer | Start at applicant nodes → traverse `-[:Supplies]->{1,2}` **forward** to measure downstream protection |
| **2. Micro-Producer & Supply Continuity** | Upstream supplier/manufacturer is quietly failing; nobody has applied yet | Community lender / co-op coordinator | Search across the corridor for non-obvious upstream nodes with high multi-hop reach (`5 <= exposed_2hop <= 25`) |
| **3. Anchor Closure** | Large employer block announces departure in 90 days; no applicants yet | City officer acting pre-emptively | **Two-stage directional shift:** Follow `(:Employer)-[:DrawsFootfall]->(:Business)` **forward** to hit retail/cafés, then `<-[:Supplies]-(:Business)` **backward** to find upstream suppliers losing their buyers |

---

## 4. Data Architecture (`a4i_econ` Dataset in BigQuery)

### Real vs. Modeled Data (Judges Check This!)

| Table | Graph Role | Primary Key / Endpoints | Properties | Reality Status |
|---|---|---|---|---|
| `businesses` | **Node** (`Business`) | `business_id` (`ttxid`) | `name`, `legal_name`, `address`, `zip`, `naics`, `naics4`, `corridor`, `latitude`, `longitude` | **100% Real** (SF Registered Business Locations, PDDL; filtered to drop sole proprietors & residential `Apt/Unit/Ste/#` addresses) |
| `employer_blocks` | **Node** (`Employer`) | `block_id` (15-char GEOCODE) | `tract` (11-char), `jobs` (`INT64`), `lat`, `lon` | **Real job counts** (Census LEHD LODES WAC), **approximate location** (placed at census tract internal point) |
| `supplies` | **Edge** (`Supplies`) | `edge_id` (`supplier_id\|buyer_id`), `supplier_id` → `buyer_id` | `intensity` (`FLOAT64`), `metres` (`FLOAT64`) | **Rates Real, Pairing Modeled:** Industry-level direct requirements ($A_{ij} = \text{Use}_{ij}/X_j$) from BEA Use tables are real federal statistics; pairing co-located businesses ($\le 1200\text{m}$, coeff $\ge 0.005$, top 5 suppliers/buyer, dropping top 10% ubiquitous industries) is modeled |
| `draws_footfall_from` | **Edge** (`DrawsFootfall`) | `edge_id` (`block_id\|business_id`), `block_id` → `business_id` | `worker_share` (`FLOAT64`), `metres` (`FLOAT64`) | **Job Counts Real, Pairing Modeled:** LEHD block jobs allocated equally across consumer-facing businesses (NAICS `44, 45, 71, 72, 81`) within $500\text{m}$ |
| `borrowed_from` | **Edge** | `business_id` → `bank_name` | `gross_approval`, `approval_date`, `loan_status`, `charged_off` (`BOOL`) | **100% Real** (SBA 7(a) FOIA records, FY2020–present). Sparse match rate, but `charged_off = TRUE` is the **only ground-truth business failure outcome** in the dataset |
| `tract_demographics` | **Attribute Table** | `geo_id` (11-char, `LPAD` with `'0'`) | `total_pop`, `median_income`, `poverty_rate`, `no_vehicle_rate`, `assistance_rate` | **100% Real** (ACS 5-Year Estimates via BigQuery public datasets) |

---

## 5. Available San Francisco Corridors

| Corridor | Businesses | Industries | Suppliers w/ 2-Hop Depth | Tracts | Poverty Rate | Notes |
|---|---:|---:|---:|---:|---:|---|
| **Central Market** *(Default)* | 230 | 65 | **86** | 7 | **22%** | Best depth + highest need tracts for equity audit |
| **Chinatown** | 413 | 71 | 37 | 9 | — | High business count, lower 2-hop supplier ratio |
| **Market/Castro** | 314 | 62 | 57 | 8 | — | Second deepest cascade network |
| **Mission Street** | 174 | 50 | 35 | **20** | — | Broadest tract coverage |
| **Union Street** | 153 | 39 | 41 | 5 | — | Solid depth for mid-sized corridor |
| **North Beach** | 148 | 35 | 18 | 4 | 13% | Known duplicate registration example (`Graffeo Coffee`) |
| **Parkside Taraval** | 109 | 38 | 19 | 4 | — | Smaller residential-commercial strip |
| **24th St** | 98 | 33 | 22 | 5 | — | Compact corridor with good 2-hop ratio |
| **Geary Boulevard** | 92 | 29 | 17 | 5 | — | Lower industry diversity |
| **West Portal** | 90 | 36 | 14 | 1 | — | Only 1 tract — cannot support a multi-tract equity audit |

---

## 6. Technical Stack & BigQuery Property Graph Traps

### Required Stack
- **Python + ADK (Agent Development Kit)**
- **Gemini** for multi-grant reasoning and Grant Memo synthesis
- **BigQuery + BigQuery Property Graph (GQL)** *(Requires Enterprise or Enterprise Plus reservation `a4i-graph` with 0 baseline slots and 50 autoscale max slots — created by `scripts/load.sh` or Notebook Section 1b)*
- **At least one Google-managed MCP server** (BigQuery built-in MCP server or **MCP Toolbox for Databases** on Cloud Run with `min-instances=1`)
- **At least one custom Python / Toolbox tool** (wrapping multi-hop cascade traversal, path weighting, and grant allocation logic)
- **Deployed to Google Cloud** (Cloud Run or Agent Runtime)

### Reference Property Graph DDL
```sql
CREATE OR REPLACE PROPERTY GRAPH a4i_econ.LocalEconomy
  NODE TABLES (
    a4i_econ.businesses
      KEY (business_id)
      LABEL Business PROPERTIES (business_id, name, naics4, zip, latitude, longitude),
    a4i_econ.employer_blocks
      KEY (block_id)
      LABEL Employer PROPERTIES (block_id, jobs)
  )
  EDGE TABLES (
    a4i_econ.supplies
      KEY (edge_id)
      SOURCE KEY (supplier_id) REFERENCES businesses (business_id)
      DESTINATION KEY (buyer_id) REFERENCES businesses (business_id)
      LABEL Supplies PROPERTIES (intensity, metres),
    a4i_econ.draws_footfall_from
      KEY (edge_id)
      SOURCE KEY (block_id) REFERENCES employer_blocks (block_id)
      DESTINATION KEY (business_id) REFERENCES businesses (business_id)
      LABEL DrawsFootfall PROPERTIES (worker_share, metres)
  );
```

### The Seven Traps (From Notebook Section 13)
1. **Two naming rules in DDL:** In `NODE TABLES` / `EDGE TABLES`, use `a4i_econ.businesses` (dataset-qualified, **no backticks**). In `REFERENCES`, use `REFERENCES businesses (business_id)` (**no dataset prefix**).
2. **Visualization requires `TO_JSON(p)`:** Graph visualization only renders paths returned via `TO_JSON(p) AS paths`.
3. **2 MB visualization limit:** Notebook renders cap at 2 MB; use `ANY SHORTEST` and `LIMIT`.
4. **Duplicate element keys silently multiply paths:** BigQuery does not enforce `KEY` uniqueness—always verify `COUNT(DISTINCT key) == COUNT(*)` before creating the graph.
5. **Global property name types:** Property names are global across all labels in a graph. That is why `employer_blocks` uses `jobs` (`INT64`) while `draws_footfall_from` uses `worker_share` (`FLOAT64`).
6. **Depth saturation at 3 hops:** In Central Market, `{1,3}` from a connected node reaches 200 of 230 businesses. Default to `{1,2}` and justify going deeper.
7. **Spanner Graph vs. BigQuery Graph docs:** Do not use Spanner-only GQL functions (`IS_ACYCLIC`, `IS_TRAIL`, `PROPERTY_EXISTS`). Only use `/bigquery/docs/` references.
8. **No `HAVING` in GQL:** Chain statements with `NEXT` followed by `FILTER` to filter on aggregated hop counts.

---

## 7. Required Output Artifact: The Grant Memo

Every run should produce a decision-ready **Grant Memo** containing:
1. **Recipient & Amount:** Business name, address, and recommended dollar grant.
2. **Downstream Cascade Protected:** Named downstream businesses, hop distance, and link strength (`intensity` or `worker_share`).
3. **Explicit Traversal Shown:** The actual GQL traversal paths (`p`).
4. **Runner-Up Comparison:** Why this recipient beat the runner-up candidate.
5. **Explicit Assumptions:** What the grant amount is assumed to change (e.g., survival probability shift).
6. **Evidence Provenance:** One clear sentence distinguishing real data (registrations, SBA loans/charge-offs, ACS, LEHD totals) from modeled pairings (BEA supply edges, footfall allocation).
7. **Neighborhood Demographics:** ACS tract poverty, vehicle access, and public assistance rates where the benefit lands.

---

## 8. Equity Audit & Differentiators ("Rigor & Judgment" = 25% of Score)

- **Mechanical Industry Bias:** Because supply edges come from BEA input-output tables, input-heavy industries (restaurants, light manufacturing) accumulate far more edges than personal service businesses (barbers, salons). Running the allocator across the corridor and comparing recommended industries vs. corridor baseline—and reporting that mechanical skew—is explicitly rewarded by judges.
- **SBA Charge-Off Ground Truth:** Check whether businesses your model flags as fragile match the industries/profiles of real historical SBA loan charge-offs (`borrowed_from.charged_off = TRUE`).
- **Entity Deduplication:** Registry records sometimes split one business across two `ttxid` rows (e.g., `Graffeo Coffee Roasting Company Inc` and `Graffeo Coffee Roasting Co.`), splitting its downstream cascade.
- **High-Value Add-On Idea — Conversational Intake Agent:** Since no public dataset records local B2B supplier links, an intake mode where a business owner describes their suppliers in natural language (including *replaceability*) and writes real verified edges back into BigQuery closes the challenge's #1 limitation.
