# 6-Slide Pitch Deck & 3-Minute Video Script
## Agents for Impact 2026 — Challenge 03: Community Economic Resilience & Micro-Grants (`Market/Castro`, SF)

---

## Part 1: 6-Slide Pitch Deck Structure

### Slide 1: The Problem — Why Ranking Businesses by Distress Fails
* **Headline:** When a Keystone Business Fails, the Cascade Hits Storefronts That Never Applied.
* **Visual:** `Market/Castro` corridor map (`1,566` raw SF Socrata filings $\rightarrow$ `327` privacy-filtered storefronts, `1,199` BEA `Supplies` edges, `677` LODES `DrawsFootfall` edges).
* **Key Takeaway:** Allocating `$50,000` by ranking individual distress or naive graph degree centrality fails in two ways:
  1. **Data Hygiene Traps:** Naive degree centrality picks **Echo Chunk Inc.** (`235` reach — a virtual mailbox at `2261 Market St` shared by `140` shell/remote entities) or **Primo** (`95` reach — a mechanical BEA monopoly artifact as the sole NAICS `3121` manufacturer).
  2. **Subgraph Overlap Trap:** Funding the top 3 or 4 businesses from a ranked list pays twice to protect the exact same downstream neighbors.

### Slide 2: System Architecture — BigQuery Property Graph (`GQL`) + Google ADK Multi-Agent
* **Headline:** Genuine Multi-Hop Graph Traversal (`GRAPH a4i_econ.LocalEconomy`) Orchestrated by 3 Specialist ADK Agents.
* **Visual:**
  - **Data Layer:** 6 public sources $\rightarrow$ `CREATE OR REPLACE PROPERTY GRAPH a4i_econ.LocalEconomy` (`Business` & `EmployerBlock` nodes; `Supplies`, `DrawsFootfall`, `BorrowedFrom` edges; `LPAD(geo_id, 11, '0')` ACS Census Tract join).
  - **Multi-Agent Layer (`agent/agent.py`):** `root_agent` orchestrating `graph_cascade_analyst`, `equity_bias_auditor`, and `grant_portfolio_defender` + BigQuery MCP Toolset.
  - **Defense Console Layer (`agent/static/index.html`):** Live SVG `TO_JSON(p)` path renderer, $\Delta P$ survival sliders, Track 3 shock simulator, and `+10 Bonus` merchant supplier verification.

### Slide 3: Data Hygiene & Bias Audit — Catching What Naive Centrality Misses
* **Headline:** Exposing Virtual Mailbox Hubs (`2261 Market St`), Single-Supplier Monopolies & Duplicate DBAs.
* **Key Proof Points from `Market/Castro`:**
  - **Virtual Mailbox Hub Filter:** Caught `140` filings at `2261 Market St` and `21` at `584 Castro St` that use bare 4-digit PMB numbers (`2261 Market Street 4303`) to evade standard `apt|ste|unit|#` regexes.
  - **Path-Level Purity Audit:** Proved why **Cafe Du Nord** (`2174 Market St E`, `28` raw 2-hop reach) drops to `#15`: `5 of its 6` direct Hop-1 buyers and `23 of its 28` total 2-hop nodes (`82%`) are virtual mailbox entities at `2261 Market St`!
  - **Entity Resolution & Ground Truth:** Linked duplicate DBAs (`The Castro` at `429` & `449 Castro St`, `Mudpuppy's`, `Midnight Sun`) and `2` verified SBA 7(a) charge-offs (`Castro Tarts Cafe And Bakery` `$50k` and `Jake's Castro Kitchen` `$85k`).

### Slide 4: The 7-Part Friday Committee Defense — Why `Theatre Rhinoceros` + `Canela`
* **Headline:** Subgraph-Deduplicated Portfolio: Maximum Physical Reach, Zero Overlap, Full Survival Runway.
* **The Subgraph Overlap Proof (`optimize_corridor_portfolio`):**
  - **Grantee #1 — Theatre Rhinoceros (`1328524-03-231`, `4229 18th St`, `NAICS 7111`):** `KeystoneScore = 0.3461`, `0.9037` 1-hop intensity, protects **12 downstream nodes (`+5` unique physical storefronts)** including `The Castro` (`429/449 Castro St`) and `Cafe Du Nord` (`2174 Market St E`).
  - **Grantee #2 — Canela (`0458630-01-001`, `2272 Market St`, `NAICS 7225`):** `KeystoneScore = 0.2927`, `88.9%` brick-and-mortar purity, adds **`+8` new unique physical storefronts (`0%` overlap with `#1`)**.
  - **Why Stop at 2 for a `$50,000` Pool:** `#3 The Castro` is **91.7% redundant** (`11 of 12` nodes already protected by `#1`) and `#4 Hi Tops` is **100% redundant** (`8 of 8` nodes already protected by `#2`). Stopping at 2 keeps both grants (`$27k–$34k` + `$16k–$23k`) above the **`$15,000` minimum effective survival runway floor**.

### Slide 5: Track 3 Two-Direction Anchor Shock & ACS Equity Context
* **Headline:** Simulating Employer Block Closures Forward Along `DrawsFootfall` and Backward Along `Supplies`.
* **GQL Traversal:** `MATCH (anchor:EmployerBlock)<-[df:DrawsFootfall]-(b1:Business)<-[s:Supplies]-(upstream:Business)`
* **Findings:** If Anchor Block `060750171011001` (`400 Castro / Market Muni`, `785` LODES jobs) experiences a footfall shock, retail storefronts (`The Castro`, `Leadbetters Bake Shop`) lose weekday trade immediately, and that shock propagates backward along `<-[:Supplies]-` to upstream producers (`Theatre Rhinoceros`, `Canela`).

### Slide 6: "+10 Bonus" What's Next — Closing the Loop from Modeled BEA to Verified Invoices
* **Headline:** Turning Every Grant Application into Verified Supply-Chain Ground Truth.
* **Honest Disclosure:** Today, `Supplies` edges are modeled from BEA Make-Use tables $\times$ exponential distance decay ($\lambda = 500\text{m}$).
* **Live Product Feature (`add_verified_merchant_supplier`):** When a merchant submits 3 local supplier invoices during grant intake, our console upgrades the edge to `MERCHANT_VERIFIED` (`is_verified = true`), emits the BigQuery `MERGE INTO a4i_econ.supplies` DML statement, and recalculates corridor cascade scores in real time.

---

## Part 2: 3-Minute Video Script (3 Team Members)

* **`0:00 – 0:35` (Member 3 — The Hook & Live Console Overview):**
  - *"In small-business relief, funding a ranked list of distressed applicants misses the one thing that makes a commercial corridor an economy: storefronts hold each other up. We built the Market/Castro Economic Resilience & Micro-Grant Defense Console on BigQuery Property Graph and Google ADK."*
  - Show the top KPI strip (`327` filtered storefronts from `1,566` raw filings, `1,199` `Supplies` edges, `677` `DrawsFootfall` edges, `9` SBA 7(a) loans with `2` charge-offs).

* **`0:35 – 1:25` (Member 1 — BigQuery GQL Traversal & Data Hygiene Traps):**
  - Switch to **Tab 2 (Bias & Equity Audit)** and click **Inspect `TO_JSON(p)` & GQL** on Tab 1.
  - *"When we ran `ANY SHORTEST` GQL traversals on `a4i_econ.LocalEconomy`, naive centrality surfaced two critical traps: first, `Echo Chunk Inc.` with 235 reach is a virtual mailbox at `2261 Market St` shared by 140 entities using bare 4-digit PMB numbers. Second, `Primo` with 95 reach is a mechanical BEA monopoly artifact as the corridor's sole NAICS 3121 manufacturer. Even `Cafe Du Nord`'s 28 reach is 82% virtual mailboxes at `2261 Market St`."*

* **`1:25 – 2:20` (Member 2 — Multi-Agent Defense Memo & Subgraph-Deduplicated Portfolio):**
  - Show **Tab 1 (7-Part Defense Memo + Multi-Business Portfolio Optimizer)**.
  - *"Our ADK Multi-Agent Orchestrator coordinates three specialist agents to build the 7-Part Friday Committee Defense Memo. Using Greedy Subgraph Deduplication, we prove why splitting the `$50,000` pool across `#1 Theatre Rhinoceros` (`4229 18th St`, Cultural Anchor) and `#2 Canela` (`2272 Market St`, Hospitality Anchor) protects 13 unique physical storefronts and 21 total downstream nodes with 0% overlap—whereas adding `#3 The Castro` is 91.7% redundant and `#4 Hi Tops` is 100% redundant. And if a city scales the pool to `$75k` or `$100k`, the optimizer dynamically adds non-overlapping sectors while enforcing a `$15,000` minimum survival grant floor."*

* **`2:20 – 3:00` (Member 3 — Track 3 Anchor Shock & +10 Bonus Live Merchant Intake):**
  - Click **Tab 3 (Track 3 Anchor Closure Simulator)**, then **Tab 4 (+10 Bonus Live Merchant Supplier Intake)** and click **Record Verified Edge & Recompute Graph Cascade**.
  - *"In Tab 3, our two-direction GQL query traces how an employer shock at Castro Station hurts footfall-dependent storefronts and travels backward along `Supplies` to upstream producers. Finally, in Tab 4, we solve the biggest limitation of modeled BEA data: as merchants submit supplier invoices during grant intake, our agent upgrades modeled edges to `MERCHANT_VERIFIED` ground truth, generates the BigQuery `MERGE` DML, and recomputes the corridor cascade live."*
