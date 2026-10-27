# ATL8 — Grant Officer UI & ADK Agent (`agent/`)

**Challenge 3: Community Economic Resilience & Micro-Grants (Agents for Impact 2026)**  
**Developer 2 Deliverable:** Cloud Run Deployment (`--min-instances=1`) + Focused Grant Officer Decision Support UI + ADK Agent (`grant_officer_agent`).

---

## 1. Pre-Configured Qwiklabs / Cloud Run Environment Values

Picked directly from your Qwiklabs Cloud Run environment (`remote-browser-vm1`):

| Setting | Value |
|---|---|
| **GCP Project ID** | `qwiklabs-gcp-03-46ba9aeed89b` |
| **GCP Project Number / Namespace** | `187574395280` |
| **Cloud Run Region** | `us-east1` |
| **Runtime Service Account** | `187574395280-compute@developer.gserviceaccount.com` |
| **VPC Access Connector** | `projects/qwiklabs-gcp-03-46ba9aeed89b/locations/us-east1/connectors/shared-cloudrun-connector` |
| **VPC Egress** | `all-traffic` |
| **Min / Max Instances** | `--min-instances=1` / `--max-instances=2` (prevents cold starts during live demo) |
| **Container Port / Timeout** | `8080` / `300s` |
| **BigQuery Property Graph** | `qwiklabs-gcp-03-46ba9aeed89b.a4i_econ.LocalEconomy` (`US` multi-region) |

---

## 2. One-Command Cloud Run Deployment (`--min-instances=1`)

From the repository root in Cloud Shell or your Qwiklabs VM:

```bash
bash agent/deploy.sh
```

Or run the `gcloud run deploy` command directly:

```bash
gcloud run deploy grant-officer-agent \
  --source ./agent \
  --project qwiklabs-gcp-03-46ba9aeed89b \
  --region us-east1 \
  --service-account 187574395280-compute@developer.gserviceaccount.com \
  --vpc-connector projects/qwiklabs-gcp-03-46ba9aeed89b/locations/us-east1/connectors/shared-cloudrun-connector \
  --vpc-egress all-traffic \
  --min-instances 1 \
  --max-instances 2 \
  --concurrency 20 \
  --cpu 1000m \
  --memory 1Gi \
  --timeout 300 \
  --port 8080 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=qwiklabs-gcp-03-46ba9aeed89b,GOOGLE_CLOUD_LOCATION=us-east1,GOOGLE_GENAI_USE_VERTEXAI=TRUE,BQ_DATASET=a4i_econ,BQ_GRAPH=LocalEconomy,BQ_LOCATION=US" \
  --allow-unauthenticated
```

You can also deploy declaratively using the Knative service spec (`agent/service.yaml`):

```bash
gcloud run services replace agent/service.yaml \
  --project qwiklabs-gcp-03-46ba9aeed89b \
  --region us-east1
```

---

## 3. Focused Grant Officer UI Features

Served at `/` (`agent/static/index.html`) via FastAPI (`agent/main.py`):

1. **Corridor, Budget, Track & Split Strategy Selector**:
   - **All 10 Official SF Corridors** from the pre-filtered snapshot (`Central Market`, `Chinatown`, `Market/Castro`, `Mission Street`, `Union Street`, `North Beach`, `Parkside Taraval`, `24th St`, `Geary Boulevard`, `West Portal`).
   - **Emergency Budget Slider + Presets** (`$15,000` to `$150,000`, default `$50,000`) and **Portfolio Split Mode** (`Split Two Grants 64%/36%`, `Single Anchor Grant 100%`, `Three-Node Portfolio 50%/30%/20%`).
   - **All 3 Challenge Tracks**:
     - *Track 1: Main Street Retail Cascade* (`-[:Supplies]->{1,2}`)
     - *Track 2: Micro-Producer & Local Supply Chain* (`NEXT FILTER exposed_2hop >= 5 AND exposed_2hop <= 25`)
     - *Track 3: Anchor Institution Closure* (`-[:DrawsFootfall]->` forward + `<-[:Supplies]-{1,2}` backward)
2. **Interactive 2-Hop Cascade Graph Visual**:
   - Color-coded SVG network diagram showing **Anchor Employer Block** (`1,420 LEHD jobs`), **Hop 0 Recommended Seed**, **Hop 1 Direct Buyers**, and **Hop 2 Indirect Cascade** nodes.
   - Displays **BEA Direct Requirements intensity (`¢/$`)**, **walking distance (`m`)**, **SBA 7(a) FOIA Charge-Off (`CHGOFF`) badges**, and **REAL vs. MODELED edge styling** (solid vs. dashed).
   - Clicking any node or candidate row inspects its node-level SBA loan status, census tract poverty rate, and 2-hop cascade.
3. **Formatted Friday Grant Memo (All 7 Required Sections)**:
   - Executive Funding Recommendation (named recipient, address, NAICS4, dollar split)
   - Hop-1 & Hop-2 Downstream Protection Breakdown (including compounded & weakest-link weights)
   - Verbatim BigQuery GQL Query (`GRAPH a4i_econ.LocalEconomy ... ANY SHORTEST ... TO_JSON(p)`)
   - Comparative Defense: Primary Pick vs. Runner-Up & **Why We Reject the Largest Centrality Hub** (`Pacific Metro Packaging & Print Corp`)
   - Explicit Survival-Probability Assumptions ($\Delta P$) & Sensitivity Analysis
   - Honest Data Provenance (Real vs. Modeled table & edge breakdown)
   - Census Tract Demographics & **3-Step Equity / BEA Mechanical Bias Audit** (explaining why service-light businesses like barbershops/dry cleaners get zero BEA supply edges)
4. **Interactive ADK Grant Officer Chat & Bonus Business Owner Supplier Intake Modal**:
   - Officers can ask follow-up questions (*"Why not fund the biggest hub?"*, *"What if the grant only shifts survival by 20%?"*, *"Which edges are real vs. modeled?"*).
   - Business owners can submit verified supplier-buyer links via the **+ Supplier Intake (Bonus)** modal to dynamically add a real edge to the graph.

---

## 4. Running Locally or with `adk web`

```bash
# Run the Focused Grant Officer UI + FastAPI server locally on port 8080:
cd agent
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080

# Or launch the native ADK Developer Web UI:
adk web . --port 8000
```
