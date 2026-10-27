# Team Decisions & Architecture Log

Use this file to record our explicit design choices (which judges grade under **Rigor & Judgment — 25 pts**).

## 1. Team Structure & Strategy (5-Person Divide & Conquer)
- **Team Size:** 5 people (smaller than the 8–10 assumed by the prompt; requires maximum code/query reuse across tracks).
- **Phase 1 Split:**
  - **Data Pair (2 people):** Data loading, validation, `CREATE PROPERTY GRAPH`, writing/testing the 3 Track GQL queries, Equity/Bias Audit queries, and SBA Charge-Off ground-truth validation.
  - **Development Pair (2 people):** ADK Agent scaffolding, MCP Toolbox / BigQuery tool integration, building the 3 track tools + Grant Memo synthesis, and UI/Deployment on Cloud Run.
  - **Person 5 (Lead / Story / Integration):** Scenario cohesion across all 3 tracks, testing edge cases ("refusal/hub-avoidance"), Grant Memo verification, pitch deck, and screen-recorded walkthrough video.
- **Track Coverage:** **All 3 Tracks** (1: Main Street Relief, 2: Micro-Producer & Supply Continuity, 3: Anchor Closure) unified under one graph and one ADK agent with three specialized entry-point tools.

## 2. Scenario & Scope
- **Chosen Corridor:** `Central Market` *(default — 230 businesses, 65 industries, 86 suppliers with 2-hop depth, 7 tracts, 22% poverty rate)*
- **Opening Scenario Statement (All-Tracks Officer Workflow):**
  > *"We run emergency economic resilience funding for San Francisco's Central Market corridor with a \$50,000 budget. In a single afternoon, we face three problems: (1) a queue of Main Street grant applicants, (2) silent upstream micro-producers who haven't applied, and (3) an announced anchor employer block departure in 90 days. Here is who is exposed across all three tracks, how we allocate the \$50,000, and what our model assumes."*

## 3. Graph & Traversal Design Decisions
- **Nodes Included:** `Business` (`a4i_econ.businesses`), `Employer` (`a4i_econ.employer_blocks`)
- **Edges Included:** `Supplies` (`a4i_econ.supplies`), `DrawsFootfall` (`a4i_econ.draws_footfall_from`), plus `borrowed_from` & `tract_demographics` joined for fragility and equity weighting.
- **Maximum Traversal Depth:** `2 hops` (`{1,2}`) — *Justification: 3 hops saturates Central Market (200/230 nodes); 2 hops captures primary and secondary cascades without noise.*
- **Path Weighting Formula:**
  - **2-hop supply path weight:** $w = \text{intensity}_1 \times \text{intensity}_2$ (direct + compounded indirect input dependency), weighted by downstream fragility (`borrowed_from` status) and census tract need (`poverty_rate`).
  - **Anchor closure path weight:** Frontline `worker_share` lost $\times$ upstream `Supplies.intensity` (measuring how much of a supplier's local buyer demand collapses when footfall disappears).
- **Hub Avoidance Rule:** Filter/penalize giant ubiquitous hubs (`exposed_2hop > 25`) that have diversified customer bases; prioritize vulnerable bottlenecks in the `5 <= exposed_2hop <= 25` band or single-supplier corridor dependencies.

## 4. Data Validation & Audit Findings
- **Validation Check Status:** `Assigned to Data Person 1`
- **Near-Duplicate Business Check:** `Assigned to Data Person 2`
- **Industry Bias Audit (Recommended % vs. Corridor Baseline %):** `Assigned to Data Person 2`
- **Tract Equity Audit (Recommended Tract Poverty Rate vs. Corridor Mean):** `Assigned to Data Person 2`
- **SBA Charge-Off Ground Truth Comparison:** `Assigned to Data Person 2`
