#!/usr/bin/env python3
"""
A4I 2026 - Challenge 3
Generates data/bea_direct_requirements.csv, the pinned BEA coefficient table.

ROI MAINTAINERS ONLY. Students never run this - the output file ships in the repo.

WHY THIS EXISTS
---------------
The notebook needs to know, for each pair of industries, how much industry A buys
from industry B per dollar of A's output. That is the "direct requirements"
(technical coefficients) matrix, and it is what makes our supply edges a modeling
choice built on a published statistic rather than an invention.

BEA's API does NOT publish Direct Requirements. Verified against a live key on
2026-08-09: the only tables it offers are Total Requirements, Domestic Supply and
Use. Total requirements already contains every indirect round of the multiplier,
so using it as an edge weight AND traversing the graph multi-hop would count the
indirect effects twice. We therefore compute direct requirements ourselves from
the Use table, the standard way:  A[i,j] = Use[i,j] / X[j].

BEA's API requires a free registration key. One key for us is fine; 150 attendees
each signing up on event morning is a help-desk queue we do not want. So we fetch
it once and pin the result, exactly as Challenge 2 pins data/foodkeeper.json.

USAGE
-----
    pip3 install requests pandas openpyxl
    export BEA_API_KEY=your-36-character-key    # https://apps.bea.gov/api/signup/
    python3 scripts/fetch_bea.py

Runs from anywhere - it resolves data/ relative to this file, not your shell's
working directory.

If table discovery cannot identify the Use table, the script
prints every table BEA offers WITH ITS FULL RAW RECORD and stops. Pick the right
id from that list and re-run with:

    export BEA_TABLE_ID=259     # 'Use of Commodities by Industries - Summary'
    python3 scripts/fetch_bea.py

OUTPUT SCHEMA - the notebook depends on exactly these three columns
-------------------------------------------------------------------
    buyer_naics4      STRING   purchasing industry, 4-digit NAICS prefix
    supplier_naics4   STRING   supplying industry, same
    coefficient       FLOAT    cents of input per dollar of buyer output
"""

import io
import os
import sys
import json
import re
from pathlib import Path

try:
    import requests
    import pandas as pd
except ImportError:
    sys.exit("Needs requests and pandas:  pip3 install requests pandas openpyxl")

API = "https://apps.bea.gov/api/data/"
CONCORDANCE_URL = ("https://www.bea.gov/sites/default/files/2023-10/"
                   "BEA-Industry-and-Commodity-Codes-and-NAICS-Concordance.xlsx")

# Resolve data/ from THIS FILE's location, not the shell's cwd. Running
# `python3 fetch_bea.py` from inside scripts/ used to write scripts/data/.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

KEY = os.environ.get("BEA_API_KEY", "").strip()
if not KEY:
    sys.exit("Set BEA_API_KEY first. Free key: https://apps.bea.gov/api/signup/")
if len(KEY) != 36:
    print(f"WARNING: BEA keys are normally 36 characters; yours is {len(KEY)}.")


def bea(**params):
    params.update(UserID=KEY, ResultFormat="JSON")
    r = requests.get(API, params=params, timeout=180)
    r.raise_for_status()
    payload = r.json().get("BEAAPI", {})
    if "Error" in payload:
        sys.exit(f"BEA API error: {json.dumps(payload['Error'], indent=2)}")
    results = payload.get("Results", {})
    if isinstance(results, dict) and "Error" in results:
        sys.exit(f"BEA API error: {json.dumps(results['Error'], indent=2)}")
    return results


def row_text(row):
    """Every string value in a record, lowercased and joined.

    BEA is not consistent about what it calls the human-readable field - it has
    used Description, Desc, and TableName across datasets, and for InputOutput it
    returned None for 'Description' entirely. So we stop guessing field names and
    search the whole record.
    """
    return " ".join(str(v).lower() for v in row.values() if v is not None)


def row_key(row):
    for k in ("Key", "key", "TableID", "TableId"):
        if row.get(k) is not None:
            return str(row[k])
    return None


def extract_rows(res):
    """Pull data rows out of a BEA Results payload, whatever shape it arrives in.

    BEA is not consistent here either. `Results` comes back as a dict for some
    requests and as a LIST for others - Year='ALL' on InputOutput returns a list
    with one result set per year, each carrying its own 'Data' array. A third
    variant returns the data rows directly as the list. Handle all three rather
    than assuming, and say what we saw if none of them fit.
    """
    if isinstance(res, dict):
        return res.get("Data", []) or []
    if isinstance(res, list):
        rows = []
        for item in res:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("Data"), list):
                rows.extend(item["Data"])
            elif any(k in item for k in ("RowCode", "ColCode", "DataValue")):
                rows.append(item)
        return rows
    return []


def describe_shape(res, limit=1200):
    """Diagnostic for when extract_rows finds nothing."""
    if isinstance(res, list):
        out = [f"Results is a LIST of {len(res)} item(s)."]
        for i, item in enumerate(res[:3]):
            if isinstance(item, dict):
                out.append(f"  [{i}] dict keys: {list(item.keys())}")
                for k, v in item.items():
                    if isinstance(v, list):
                        out.append(f"       {k}: list of {len(v)}; first = "
                                   f"{json.dumps(v[0])[:200] if v else 'empty'}")
            else:
                out.append(f"  [{i}] {type(item).__name__}: {str(item)[:160]}")
        return "\n".join(out)
    if isinstance(res, dict):
        return (f"Results is a DICT with keys: {list(res.keys())}\n"
                f"{json.dumps(res, indent=2)[:limit]}")
    return f"Results is a {type(res).__name__}: {str(res)[:limit]}"


def find_use_table():
    """Find the Use table (commodities x industries), Summary level.

    NOTE, and this cost us a run: BEA's API does NOT publish a Direct
    Requirements table. It offers Total Requirements, Supply, and Use, and
    nothing else. Verified 2026-08-09 against a live key - the ten tables the
    API returns are Total Requirements (6 variants), Domestic Supply (2), and
    Use (2).

    We want DIRECT requirements, not total. Total requirements already contains
    every indirect round of the multiplier. Using it as an edge weight and then
    traversing the graph multi-hop would count the indirect effects twice - once
    inside each coefficient, once along the path - and produce inflated cascade
    numbers that look entirely plausible.

    So we compute the direct-requirements (technical coefficients) matrix
    ourselves, the standard way:

        A[i, j] = Use[i, j] / X[j]

    where X[j] is total output of industry j. That is what BEA does to produce
    the Direct Requirements table it publishes on its website but not via API.
    """
    override = os.environ.get("BEA_TABLE_ID", "").strip()
    if override:
        print(f"Using BEA_TABLE_ID override: {override}")
        return override, "(supplied via BEA_TABLE_ID)"

    res = bea(method="GetParameterValues", DataSetName="InputOutput",
              ParameterName="TableID")
    rows = res.get("ParamValue", [])
    if not rows:
        sys.exit(f"BEA returned no TableID values. Raw response:\n"
                 f"{json.dumps(res, indent=2)[:2000]}")

    scored = []
    for row in rows:
        text = row_text(row)
        if "use of commodities" in text:
            # Summary (~71 industries) over Sector (~15). Sector is far too
            # coarse - a corridor would collapse into a handful of industries.
            scored.append((3 * ("summary" in text), row_key(row), row))

    if scored:
        scored.sort(key=lambda t: -t[0])
        print("Candidate Use tables:")
        for s, k, r in scored:
            print(f"  [{s}] {k}: {row_text(r)[:110]}")
        return scored[0][1], row_text(scored[0][2])[:160]

    print("Could not identify a Use table. BEA returned these - full raw records:\n")
    for row in rows:
        print(f"  {json.dumps(row)}")
    print("\nSet BEA_TABLE_ID to the 'Use of Commodities by Industries - Summary' id.")
    sys.exit(1)


def load_concordance():
    """BEA industry code -> 4-digit NAICS. Written out so it can be audited.

    Deliberately does NOT use pandas' .str accessor anywhere. Excel sheets have
    ragged, mixed-type cells - an empty cell arrives as a float NaN even under
    dtype=str - and .str on a column pandas has decided is float raises. Every
    cell is coerced with str() one at a time instead. Slower, and it cannot fail
    on a shape we did not anticipate.
    """
    print("Fetching BEA/NAICS concordance...")
    r = requests.get(CONCORDANCE_URL, timeout=180)
    r.raise_for_status()
    try:
        sheets = pd.read_excel(io.BytesIO(r.content), sheet_name=None,
                               dtype=object, header=None)
    except ImportError:
        sys.exit("Reading .xlsx needs openpyxl:  pip3 install openpyxl")

    def cells(frame, i):
        return [str(v).strip().lower() if v is not None else "" for v in frame.iloc[i].values]

    best = None
    for name, raw in sheets.items():
        if raw.empty:
            continue
        for hdr in range(min(15, len(raw))):
            row = cells(raw, hdr)
            # The BEA concordance workbook has a column per aggregation level
            # (Sector / Summary / U.Summary / Detail) plus a NAICS column. We
            # want Summary, because the Use table we pulled is summary level.
            bea_col = next((i for i, v in enumerate(row) if v == "summary"), None)
            if bea_col is None:
                bea_col = next((i for i, v in enumerate(row)
                                if "summary" in v or ("bea" in v and "code" in v)), None)
            nai_col = next((i for i, v in enumerate(row) if "naics" in v), None)
            if bea_col is None or nai_col is None:
                continue

            pairs = []
            for i in range(hdr + 1, len(raw)):
                vals = raw.iloc[i].values
                code = str(vals[bea_col]).strip() if bea_col < len(vals) else ""
                nai = str(vals[nai_col]).strip() if nai_col < len(vals) else ""
                if not code or code.lower() in ("nan", "none", ""):
                    continue
                # One BEA code can cover several NAICS: "311, 312" or "3361-3363".
                # Keep them all - dropping the extras silently loses whole
                # industries from the graph.
                for token in re.split(r"[,;/]| and ", nai):
                    m = re.search(r"(\d{2,6})", token)
                    if m:
                        pairs.append((code, m.group(1)[:4]))
            df = pd.DataFrame(pairs, columns=["bea_code", "naics4"]).drop_duplicates()
            if len(df) and (best is None or len(df) > len(best[2])):
                best = (name, hdr, df)

    if best is None or len(best[2]) < 20:
        print("\nCould not locate a BEA-code/NAICS mapping. Workbook contents:")
        for name, raw in sheets.items():
            print(f"\n  sheet {name!r}: {raw.shape[0]} rows x {raw.shape[1]} cols")
            for i in range(min(4, len(raw))):
                print(f"    row {i}: {[str(v)[:28] for v in raw.iloc[i].values[:10]]}")
        sys.exit("Adjust load_concordance() using the dump above.")

    name, hdr, df = best
    print(f"  using sheet {name!r}, header row {hdr}")
    print(f"  {len(df)} BEA-code -> NAICS4 pairs, "
          f"{df.bea_code.nunique()} distinct BEA codes")
    print(f"  sample: {df.head(5).values.tolist()}")
    return df


def main():
    table_id, desc = find_use_table()
    print(f"\nUsing TableID {table_id}: {desc}\n")

    res = bea(method="GetData", DataSetName="InputOutput",
              TableID=table_id, Year="ALL")
    rows = extract_rows(res)
    if not rows:
        sys.exit(f"BEA returned no usable data rows for table {table_id}.\n"
                 f"{describe_shape(res)}")

    df = pd.DataFrame(rows)
    print(f"{len(df):,} raw cells")
    print(f"Columns BEA returned: {list(df.columns)}")

    for needed in ("RowCode", "ColCode", "DataValue"):
        if needed not in df.columns:
            sys.exit(f"Expected column {needed!r} and BEA did not return it. "
                     f"Got: {list(df.columns)}")

    if "Year" in df.columns:
        year = df["Year"].max()
        df = df[df.Year == year]
        print(f"Newest year: {year}  ({len(df):,} cells)")
    else:
        year = "unknown"

    df["value"] = pd.to_numeric(
        df["DataValue"].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    df = df[df.value.notna()]

    # --- the denominator: total output of each industry (column) -------------
    # Discover the row rather than hardcoding a code. BEA's row for this has been
    # spelled several ways across vintages.
    desc_col = next((c for c in ("RowDescr", "RowDescription", "RowName")
                     if c in df.columns), None)
    if desc_col is None:
        sys.exit(f"No row-description column to find total output with. "
                 f"Columns: {list(df.columns)}")

    labels = df[desc_col].astype(str)
    mask = labels.str.contains("total industry output", case=False, na=False)
    if not mask.any():
        mask = labels.str.fullmatch(r"\s*total output\s*", case=False, na=False)
    if not mask.any():
        print("\nCould not find a total-industry-output row. Row labels present:")
        for lbl in sorted(labels.unique())[:80]:
            print(f"  {lbl}")
        sys.exit("Adjust the total-output matcher using the list above.")

    out_row = df[mask]
    print(f"Total-output row: {out_row[desc_col].iloc[0]!r} "
          f"(RowCode {out_row.RowCode.iloc[0]}), {len(out_row)} industry columns")
    X = dict(zip(out_row.ColCode.astype(str).str.strip(), out_row.value))

    # --- A[i,j] = Use[i,j] / X[j] --------------------------------------------
    inter = df[~mask].copy()
    inter["denom"] = inter.ColCode.astype(str).str.strip().map(X)
    inter = inter[inter.denom.notna() & (inter.denom > 0) & (inter.value > 0)]
    inter["coefficient"] = inter.value / inter.denom
    print(f"Intermediate cells with a valid denominator: {len(inter):,}")

    conc = load_concordance()

    inter["_row"] = inter["RowCode"].astype(str).str.strip()
    inter["_col"] = inter["ColCode"].astype(str).str.strip()
    sup = conc.rename(columns={"bea_code": "_row", "naics4": "supplier_naics4"})
    buy = conc.rename(columns={"bea_code": "_col", "naics4": "buyer_naics4"})

    before_cells = inter[["_row", "_col"]].drop_duplicates().shape[0]
    mapped = (inter[["_row", "_col", "coefficient"]]
              .merge(sup, on="_row").merge(buy, on="_col"))
    after_cells = mapped[["_row", "_col"]].drop_duplicates().shape[0]
    print(f"Use cells whose BOTH industry codes mapped to NAICS: {after_cells:,} "
          f"of {before_cells:,} ({after_cells / max(before_cells, 1):.0%})")
    print(f"  expanded to {len(mapped):,} NAICS-level pairs "
          f"(one BEA code can cover several NAICS)")
    out = mapped[["supplier_naics4", "buyer_naics4", "coefficient"]]
    print("  (value-added rows and final-demand columns do not map to NAICS and")
    print("   are dropped here on purpose - they are not industries.)")
    if len(mapped) < 100:
        sys.exit("Almost nothing mapped. The concordance picked the wrong columns - "
                 "inspect data/bea_naics_concordance.csv before trusting anything.")

    out = mapped[mapped.supplier_naics4 != mapped.buyer_naics4]
    out = (out.groupby(["buyer_naics4", "supplier_naics4"], as_index=False)
              .coefficient.max()
              .sort_values("coefficient", ascending=False))

    # A technical coefficient is a share of output - it cannot exceed 1.
    if out.coefficient.max() > 1.0:
        print(f"\nWARNING: max coefficient is {out.coefficient.max():.3f}, above 1.0.")
        print("A direct-requirements coefficient is cents per dollar of output and")
        print("cannot exceed 1. The denominator is probably wrong. Do NOT commit.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    coeff_path = DATA_DIR / "bea_direct_requirements.csv"
    conc_path = DATA_DIR / "bea_naics_concordance.csv"
    out.to_csv(coeff_path, index=False)
    conc.to_csv(conc_path, index=False)

    print()
    print(f"WROTE {coeff_path}  ({len(out):,} industry pairs)")
    print(f"WROTE {conc_path}  ({len(conc):,} code mappings)")
    print(f"  buying industries   : {out.buyer_naics4.nunique()}")
    print(f"  supplying industries: {out.supplier_naics4.nunique()}")
    print(f"  coefficient range   : {out.coefficient.min():.5f} to {out.coefficient.max():.5f}")
    print()
    print("SANITY CHECK - the strongest relationships. These should look")
    print("economically sensible. If they do not, the concordance mapped wrong")
    print("and you should NOT commit these files.")
    print(out.head(12).to_string(index=False))
    print()
    print(f"Source: BEA Input-Output Accounts, Use table {table_id}, year {year},")
    print("normalized by total industry output to give direct requirements.")
    print("License: public domain (https://bea.gov/help/faq/145). Commit both files.")


if __name__ == "__main__":
    main()
