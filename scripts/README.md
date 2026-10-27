# scripts/

## `load.sh`

A headless fallback that reaches the same end state as `notebooks/c3_01_load_explore.ipynb`,
rebuilding every BigQuery table from a pre-staged snapshot in Cloud Storage.

```bash
bash scripts/load.sh                    # defaults to central-market
bash scripts/load.sh 24th-st
bash scripts/load.sh --list             # show available corridors
```

Invoke it with `bash`, not `./scripts/load.sh`—that way it works regardless of whether the file
arrived with its executable bit set, which depends on how your repo was created.

Safe to run repeatedly. Every table load uses `--replace`, so the script is idempotent and
interrupting it breaks nothing.

**Use the notebook if you can.** This script gets you the tables without the teaching, and one
piece of that teaching—which of the connections in your graph are measured and which are
modeled—is something judges look for directly.

## `fetch_bea.py`

**ROI maintainers only. Students never run this.** It generates
`data/bea_direct_requirements.csv`, which ships in the repo.

```bash
pip3 install requests pandas openpyxl
export BEA_API_KEY=your-36-character-key      # free: https://apps.bea.gov/api/signup/
python3 scripts/fetch_bea.py
```

It discovers the table id from the API rather than hardcoding one—BEA does not publish a list
of table ids and says so explicitly, so any literal id you find in a blog post is a guess. If
discovery fails it prints every table BEA offers, with full raw records, and stops rather than
picking one.

**Note what it fetches and why.** BEA's API does **not** expose a Direct Requirements table—only Total Requirements, Domestic Supply, and Use (verified against a live key, 2026-08-09).
Total requirements already contains every indirect round of the multiplier, so using it as an
edge weight *and* traversing the graph multi-hop would double-count. This script therefore pulls
the **Use** table and normalizes each column by that industry's total output, which is the
standard technical-coefficients calculation and gives genuine direct requirements. Edges carry
the direct effect; the graph supplies the indirect one.

It prints the ten strongest industry relationships at the end. **Read them.** If they do not look
economically sensible, the BEA-to-NAICS concordance mapped wrong and the file should not be
committed.
