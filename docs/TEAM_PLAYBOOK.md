# 5-Person Team Playbook: Completing All 3 Tracks

Because we have **5 people** instead of 8–10 and want **all three tracks complete**, we cannot afford to build three separate systems. Instead, we use **one shared Property Graph** and **one shared ADK Agent** with **three Track Tools** that all feed into the **same Grant Memo & Audit Engine**.

---

## 1. Architecture: How All 3 Tracks Share 80% of the Work

```
                       [ BigQuery Dataset: a4i_econ ]
                     [ Graph: a4i_econ.LocalEconomy ]
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│  TRACK 1 TOOL     │     │  TRACK 2 TOOL     │     │  TRACK 3 TOOL     │
│ Main Street Queue │     │  Micro-Producer   │     │  Anchor Closure   │
│                   │     │     Discovery     │     │   Shockwave       │
│ Seed: Applicants  │     │ Seed: Whole Graph │     │ Seed: Employer    │
│ Walk: Supplies    │     │ Walk: Supplies    │     │ Walk: Footfall -> │
│   forward {1,2}   │     │   forward {1,2}   │     │   <- Supplies     │
│                   │     │ Filter: 5..25 hop │     │   (reverses dir!) │
└─────────┬─────────┘     └─────────┬─────────┘     └─────────┬─────────┘
          └─────────────────────────┼─────────────────────────┘
                                    ▼
             ┌─────────────────────────────────────────────┐
             │   SHARED ENRICHMENT & SCORING LAYER         │
             │ • SBA Loan & Charge-Off Fragility Lookup    │
             │ • ACS Census Tract Need (Poverty/Vehicle)   │
             │ • Hub-Avoidance & Equity Bias Audit         │
             └──────────────────────┬──────────────────────┘
                                    ▼
             ┌─────────────────────────────────────────────┐
             │   SHARED OUTPUT: DEFENDED GRANT MEMO        │
             │ • Target Business + Grant $ + Runner-Up     │
             │ • Visualized / Named GQL Cascade Paths      │
             │ • Explicit Assumptions & Modeled Disclosure │
             └─────────────────────────────────────────────┘
```

---

## 2. Phase 1 Role Breakdown (First 90 Minutes)

### Data Person 1: Infrastructure, Graph DDL & Track 1 + Track 2 GQL
1. **Load & Reserve (Min 0–15):**
   - Run `bash scripts/load.sh central-market` in Cloud Shell (creates the `ENTERPRISE` reservation `a4i-graph` and loads all 6 tables into `a4i_econ`).
   - Run Section 12 validation checks from `notebooks/c3_01_load_explore.ipynb` to confirm unique keys (`business_id`, `edge_id`, `block_id`) and record the exact numbers for the judges.
2. **Create the Unified Property Graph (Min 15–25):**
   - Execute the `CREATE OR REPLACE PROPERTY GRAPH a4i_econ.LocalEconomy` DDL (including both `Business` and `Employer` nodes, and `Supplies` and `DrawsFootfall` edges).
3. **Deliver Track 1 & Track 2 Queries to Dev Pair (Min 25–60):**
   - **Track 1 (Main Street Queue):** Parameterized GQL query taking a list of applicant `business_id`s, walking `-[:Supplies]->{1,2}`, returning 1-hop and 2-hop exposed businesses, compounded path intensity, and JSON paths.
   - **Track 2 (Micro-Producer Discovery):** Unseeded GQL scan using `NEXT` + `FILTER exposed_2hop BETWEEN 5 AND 25` to find non-hub upstream producers with high downstream leverage.

### Data Person 2: Track 3 (Anchor Closure) GQL, SBA Ground Truth & Equity Audit
1. **Deliver Track 3 Query (Anchor Closure Forward-Then-Backward) (Min 0–40):**
   - Identify the top `employer_blocks` in `a4i_econ.employer_blocks` by `jobs`.
   - Write the two-leg GQL query:
     - **Leg 1 (Forward):** `(e:Employer)-[:DrawsFootfall]->(b1:Business)` — consumer shops losing lunch/weekday footfall.
     - **Leg 2 (Backward):** `(b1:Business)<-[:Supplies]-(b2:Business)` — upstream local suppliers who lose their buyers when `b1` suffers a footfall collapse.
2. **SBA Charge-Off Validation & Fragility Join (Min 40–65):**
   - Query `a4i_econ.borrowed_from` (and the state-wide SBA base rate from Section 6) to identify which businesses/industries in the corridor have real SBA loans or `charged_off = TRUE`.
   - Check for duplicate business registrations (same normalized name/address, split `business_id`s) so we can highlight them in the Grant Memo.
3. **Equity & Mechanical Industry-Bias Audit (Min 65–90):**
   - Write the SQL audit query comparing the industry distribution (`naics4`) and census tract `poverty_rate` / `no_vehicle_rate` of top cascade candidates against the overall corridor baseline.

---

### Dev Person 1: ADK Agent Core, MCP Connection & Tool Wrappers
1. **Scaffold `agent/` Package (Min 0–20):**
   - Set up `agent/agent.py`, `agent/tools.py`, `agent/prompts.py`, and `requirements.txt` (`google-adk`, `google-cloud-bigquery`, etc.).
   - Connect BigQuery's built-in MCP server or **MCP Toolbox for Databases** for general table lookups (`businesses`, `tract_demographics`, `borrowed_from`).
2. **Build the 3 Track Tools in `agent/tools.py` (Min 20–65):**
   - `analyze_main_street_applicants(applicant_ids: list[str], budget: float)` (Track 1)
   - `find_vulnerable_micro_producers(min_reach: int = 5, max_reach: int = 25, budget: float = 50000)` (Track 2)
   - `analyze_anchor_closure_shock(block_id: str, budget: float = 50000)` (Track 3)
   - *Note:* Start with the ready-to-use SQL/GQL templates below immediately so you are **zero-minute blocked** on Data!
3. **Build the Shared Enrichment & Audit Tool (Min 65–90):**
   - `run_equity_and_fragility_audit(recommended_business_ids: list[str])` — compares recommended recipients against corridor tract poverty rates, industry representation bias, and SBA charge-off records.

### Dev Person 2: System Prompt, Grant Memo Generator, UI & Early Cloud Run Deploy
1. **System Prompt & Guardrails (`agent/prompts.py`) (Min 0–35):**
   - Encode the 7 grant-officer questions, the **Hub-Avoidance Rule** (when *not* to fund the biggest hub), **Refusal Logic** (what to say when an applicant is a leaf with 0 downstream edges or when two candidates are tied), and the **Grant Memo** template.
2. **Early Deployment Pipeline (Min 35–60):**
   - Containerize and deploy to **Cloud Run** (`min-instances=1` so the demo has zero cold start) and verify `adk web` / custom UI endpoint.
3. **Front-End / Demo Interface (Min 60–90):**
   - Build or configure a clean 3-tab / 3-mode view (Track 1: Main Street Queue, Track 2: Micro-Producer Radar, Track 3: Anchor Closure Simulator) that displays the **Cascade Graph Path** and the formatted **Grant Memo**.

---

### Person 5 (Team Lead / Story / Integration): Cross-Track Testing & Judge Deliverables
1. **Curate the "Golden Demo Inputs" for Each Track (Min 0–45):**
   - Pick the exact 3–5 applicant `business_id`s for Track 1 (including 1 leaf business, 1 giant robust hub we choose *not* to fund, and 1 high-leverage supplier we *do* fund).
   - Pick the best hidden micro-producer in Track 2.
   - Pick the largest `block_id` in Track 3 that triggers a 2-leg Footfall → backward Supplies cascade.
2. **Verify All 7 Officer Questions & Edge Cases (Min 45–90):**
   - Test the agent against every judge rubric item and capture the generated Grant Memos for the pitch deck and video walkthrough.

---

## 3. Ready-to-Use GQL Queries for All 3 Tracks

The Data and Dev pairs can use these exact queries as their contract starting at Minute 0:

### Step A: Unified Property Graph DDL (`a4i_econ.LocalEconomy`)
```sql
CREATE OR REPLACE PROPERTY GRAPH a4i_econ.LocalEconomy
  NODE TABLES (
    a4i_econ.businesses
      KEY (business_id)
      LABEL Business PROPERTIES (business_id, name, address, naics4, zip, latitude, longitude),
    a4i_econ.employer_blocks
      KEY (block_id)
      LABEL Employer PROPERTIES (block_id, tract, jobs, lat, lon)
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

### Track 1 Query: Main Street Relief (Applicant Queue Multi-Hop Cascade)
```sql
SELECT *
FROM GRAPH_TABLE(
  a4i_econ.LocalEconomy
  MATCH (seed:Business)-[e1:Supplies]->(hop1:Business)
  WHERE seed.business_id IN UNNEST(@applicant_ids)
  RETURN
    seed.business_id AS applicant_id,
    seed.name AS applicant_name,
    seed.address AS applicant_address,
    seed.naics4 AS applicant_naics4,
    hop1.business_id AS exposed_id,
    hop1.name AS exposed_name,
    hop1.naics4 AS exposed_naics4,
    1 AS hop_distance,
    e1.intensity AS path_weight,
    e1.metres AS step_metres
  UNION ALL
  MATCH (seed:Business)-[e1:Supplies]->(hop1:Business)-[e2:Supplies]->(hop2:Business)
  WHERE seed.business_id IN UNNEST(@applicant_ids)
    AND hop2.business_id != seed.business_id
  RETURN
    seed.business_id AS applicant_id,
    seed.name AS applicant_name,
    seed.address AS applicant_address,
    seed.naics4 AS applicant_naics4,
    hop2.business_id AS exposed_id,
    hop2.name AS exposed_name,
    hop2.naics4 AS exposed_naics4,
    2 AS hop_distance,
    (e1.intensity * e2.intensity) AS path_weight,
    (e1.metres + e2.metres) AS step_metres
);
```

### Track 2 Query: Micro-Producer & Supply Continuity (Sweet-Spot Discovery)
```sql
SELECT *
FROM GRAPH_TABLE(
  a4i_econ.LocalEconomy
  MATCH (seed:Business)-[e:Supplies]->{1,2}(exposed:Business)
  WHERE exposed.business_id != seed.business_id
  RETURN
    seed.business_id AS producer_id,
    seed.name AS producer_name,
    seed.address AS producer_address,
    seed.naics4 AS producer_naics4,
    COUNT(DISTINCT exposed.business_id) AS exposed_2hop_count
  NEXT
  FILTER exposed_2hop_count >= @min_reach AND exposed_2hop_count <= @max_reach
  RETURN
    producer_id,
    producer_name,
    producer_address,
    producer_naics4,
    exposed_2hop_count
)
ORDER BY exposed_2hop_count DESC;
```

### Track 3 Query: Anchor Closure (Forward `DrawsFootfall` → Backward `<-[:Supplies]-`)
```sql
SELECT *
FROM GRAPH_TABLE(
  a4i_econ.LocalEconomy
  MATCH (anchor:Employer WHERE anchor.block_id = @block_id)
        -[f:DrawsFootfall]->(frontline:Business)
        <-[s:Supplies]-(upstream:Business)
  RETURN
    anchor.block_id AS closing_block_id,
    anchor.jobs AS block_jobs_lost,
    frontline.business_id AS frontline_business_id,
    frontline.name AS frontline_name,
    frontline.naics4 AS frontline_naics4,
    f.worker_share AS frontline_worker_share_lost,
    upstream.business_id AS upstream_supplier_id,
    upstream.name AS upstream_supplier_name,
    upstream.address AS upstream_supplier_address,
    upstream.naics4 AS upstream_supplier_naics4,
    s.intensity AS supply_dependency_intensity,
    (f.worker_share * s.intensity) AS compounded_shock_score
)
ORDER BY compounded_shock_score DESC;
```
