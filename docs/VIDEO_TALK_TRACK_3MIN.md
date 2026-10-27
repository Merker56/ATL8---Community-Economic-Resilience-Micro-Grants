# 3-Minute Video Talk Track & Demo Script (Strict <= 2:55 Pacing)

**Team ATL8:**
- **Kiran & David** — Data Pipeline, BigQuery Property Graph (`a4i_econ.LocalEconomy`), GQL Traversals & Bias/Equity Audits
- **Venkatesh** — Front-End Dual-Console UI (`index.html` & `market_castro_console.html`), SVG `TO_JSON(p)` Graph & Leaflet Map
- **Subba & Joe** — Backend FastAPI/Cloud Run (`--min-instances=1`), Google ADK 3-Sub-Agent Orchestrator & MCP Toolset

**Pacing Budget:**
- **Total Duration:** **2 minutes 55 seconds** (strictly under the 3:00 hard cap)
- **Total Word Count:** **~425 words** (spoken at a crisp, natural 145 WPM)
- **Structure:** `0:00–0:20` Intro (20s) | `0:20–2:40` Live Demo covering Architecture, Top 5 Capabilities, Top 4 Decisions, and Constraints (2m 20s) | `2:40–3:00` Outro (20s)

---

## [0:00 – 0:20] Intro: The Challenge & Why It Matters (20 Seconds | ~48 Words)

**Speaker:** Joe *(or Single Narrator)*
**On Screen:** Title slide or top header of the live **SF OEWD Micro-Grant Resilience Console** ([`agent/static/index.html`](file:///tmp/github_repo/agent/static/index.html)) showing `Central Market` and `Market/Castro` corridor metrics.

> **Talk Track:**
> "When a neighborhood supplier closes, the balance sheet sees one empty storefront. In reality, it triggers a silent multi-hop cascade—cutting off local cafés, caterers, and event halls that never knew they were exposed. Traditional relief ranks applicants in isolation by distress. With a scarce \$50,000 budget, grant officers need to fund the businesses that **hold the corridor up**. I’m Joe, alongside Kiran and David on Data, Venkatesh on Frontend, and Subba on Backend and Agents—and this is our **Community Economic Resilience & Micro-Grant Advisor**."

---

## [0:20 – 2:40] Live Demo: Architecture, Capabilities, Decisions & Constraints (2m 20s)

### Part 1 [0:20 – 0:45] — (d) Deployed Architecture Tour (25 Seconds | ~62 Words)

**Speaker:** Subba
**On Screen:** Point to the green `Cloud Run: us-east1 | --min-instances=1 (Warm)` telemetry badge and `Graph: a4i_econ.LocalEconomy` badge in the top bar, then briefly show the 3-Sub-Agent trace panel.

> **Talk Track:**
> "Here is our live architecture deployed on **Google Cloud Run** with `--min-instances=1` to eliminate cold starts. Under the hood, Kiran and David built `a4i_econ.LocalEconomy` in **BigQuery Property Graph** over an Enterprise slot reservation—joining six datasets: DataSF business registrations, BEA Input-Output tables, Census LEHD block jobs, ACS demographics, and FOIA SBA 7(a) loans. Subba and I wired a **Google ADK Root Orchestrator** coordinating three specialist sub-agents—`graph_cascade_analyst`, `equity_bias_auditor`, and `grant_portfolio_defender`—connected via **MCP Toolbox for Databases**, powering Venkatesh’s interactive console."

---

### Part 2 [0:45 – 1:35] — (a) Top 5 Capabilities & Why They Matter (50 Seconds | ~125 Words)

**Speaker:** Venkatesh
**On Screen:**
1. Select `Central Market` (or switch via the 1-click button to `/market-castro` [`market_castro_console.html`](file:///tmp/github_repo/agent/static/market_castro_console.html)) and highlight the **SVG `TO_JSON(p)` Cascade Graph** & **Leaflet Map**.
2. Show the **4-Bucket Holistic Portfolio / Subgraph Optimizer** table.
3. Click **Track 3: Anchor Closure** (`DrawsFootfall` $\rightarrow$ backward `Supplies`).
4. Click the **Bias & Equity Audit** tab (`SBA CHGOFF` & `2261 Market St` flags).
5. Click **+ Business Owner Intake Edge** modal and the **7-Part Friday Grant Memo**.

> **Talk Track:**
> "Our console delivers five core capabilities for a city grant officer:
> **First, Multi-Hop GQL Cascade Discovery:** We execute `ANY SHORTEST` GQL traversals with `TO_JSON(p)` across all 10 SF corridors, rendering live 1-to-2 hop supply chains so officers see exactly which downstream storefronts a grant protects.
> **Second, Holistic 4-Bucket & Subgraph-Deduplicated Portfolio Allocation:** Instead of cherry-picking one winner or paying twice for overlapping neighbors, our optimizer splits the budget across Keystone Suppliers, Mid-Chain Connectors, and Frontline Storefronts—proving in `Market/Castro`, for example, that funding **Theatre Rhinoceros** plus **Canela** protects 13 unique storefronts with **0% overlap**.
> **Third, Track 3 Bi-Directional Anchor Shock:** When an employer block announces layoffs, we traverse *forward* along `DrawsFootfall` to frontline cafés and *backward* along `Supplies` to catch upstream producers before orders vanish.
> **Fourth, SBA Charge-Off & Hygiene Auditing:** We overlay real SBA 7(a) defaults to spot fragile links.
> **Fifth, Live Merchant Invoice Intake & the 7-Part Friday Memo:** Officers can record verified supplier invoices on the spot—upgrading modeled edges to ground truth—and export a decision-ready Friday Committee Memo."

---

### Part 3 [1:35 – 2:15] — (b) Top 4 Engineering & Modeling Decisions (40 Seconds | ~100 Words)

**Speaker:** Kiran & David
**On Screen:** Show the **Bias & Equity Audit** tab highlighting `2261 Market St` (140 virtual mailboxes), `Primo` / `Pacific Metro` hub exclusions, the **30% Bucket 3 Equity Reserve**, and the **\$15,000 Minimum Survival Floor**.

> **Talk Track:**
> "To make recommendations defensible, we made four critical design decisions:
> **Decision 1 — Stopping GQL at 2 Hops (`{1,2}`):** At 3 hops, the graph saturates over 85% of the corridor. Two hops isolates real primary and secondary exposure without noise.
> **Decision 2 — Hub-Avoidance & Virtual Mailbox Disqualification:** Naive degree centrality fails—it picks giant credit-worthy distributors like `Pacific Metro` (38 edges), sole-NAICS artifacts like `Primo`, or `Echo Chunk Inc.` at `2261 Market St`, where we caught **140 virtual mailbox filings** hiding behind 4-digit PMB numbers. We restrict B2B keystone grants to the `5-to-25` hop sweet spot and hold duplicate DBAs.
> **Decision 3 — Correcting BEA Mechanical Bias via a 30% Frontline Equity Reserve:** Because BEA tables assign zero outgoing supply edges to barbers, delis, and retail leaves, we dedicate 30% of the pool to high-poverty, high-footfall storefronts.
> **Decision 4 — Enforcing a \$15,000 Minimum Grant Floor:** We prevent peanut-butter spreading so every grant provides real 90-day survival runway."

---

### Part 4 [2:15 – 2:40] — (c) Honest Constraints: What It Can't Do & Why (25 Seconds | ~62 Words)

**Speaker:** David *(or Joe)*
**On Screen:** Point to the **$\Delta P$ Survival Probability Sliders** (`P(fail|No Grant)` vs `P(fail|Grant)`) and the **Evidence Provenance Disclosure** box in Part 5 & Part 6 of the Friday Memo.

> **Talk Track:**
> "Just as important is what our agent **refuses** to claim. First, no public US dataset reports commercial rent arrears or per-storefront employee headcounts—Census LEHD only reports jobs by *block*. Our agent refuses to invent storefront payrolls or lease terms, instead exposing explicit survival-probability sliders ($\Delta P$). Second, while our nodes, ACS tracts, and SBA charge-offs are 100% empirical, firm-to-firm supply and footfall pairings are modeled from BEA averages and walking distance—which is why our live invoice intake tool is essential to replace modeled edges with verified ground truth."

---

## [2:40 – 3:00] Outro: Impact Summary (20 Seconds | ~45 Words)

**Speaker:** Joe
**On Screen:** Click **Print / PDF Friday Memo** showing the complete 7-part executive output artifact.

> **Talk Track:**
> "By combining BigQuery Property Graphs, Google ADK's multi-agent orchestration, and rigorous bias auditing on Cloud Run, we give grant officers more than a centrality score—we give them a transparent, mathematically defended case they can take into Friday’s meeting and sign. From Kiran, David, Venkatesh, Subba, and Joe—thank you!"
