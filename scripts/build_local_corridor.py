#!/usr/bin/env python3
"""
A4I 2026 — Challenge 3: Community Economic Resilience & Micro-Grants
Local & BigQuery Mirror Builder for the 'Market/Castro' Corridor (San Francisco).

Reproduces the exact pipeline from notebooks/c3_01_load_explore.ipynb (Sections 3–12)
using pure Python standard library (zero heavy C-extension dependencies required),
and outputs `data/market_castro_graph.json` containing all 6 BigQuery tables:
  1. businesses           (Node table: Business)
  2. employer_blocks      (Node table: Employer)
  3. supplies             (Edge table: Supplies)
  4. draws_footfall_from  (Edge table: DrawsFootfall)
  5. borrowed_from        (Edge/Validation table: SBA 7(a) loans & charge-offs)
  6. tract_demographics   (Attribute table: ACS 5-year tract estimates with 11-char LPAD geo_id)

Also computes structural audit metadata (virtual mailbox detection at 2261 Market St &
584 Castro St, duplicate DBA registrations, and single-NAICS monopoly flags) used by
the Grant Officer Defense Console and ADK Agent.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import subprocess
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
BEA_CSV = DATA_DIR / "bea_direct_requirements.csv"
RAW_CACHE = DATA_DIR / "sf_market_castro_raw.json"
TMP_CACHE = Path("/tmp/sf_market_castro.json")
CORRIDOR = os.environ.get("CORRIDOR_NAME", "Market/Castro")
CITY = os.environ.get("CITY_NAME", "San Francisco")
STATE = os.environ.get("STATE_ABBR", "CA")
STATE_FIPS = os.environ.get("STATE_FIPS", "06")
OUT_GRAPH_JSON = Path(os.environ.get("GRAPH_JSON_PATH", str(DATA_DIR / "market_castro_graph.json")))

# Section 4 privacy & storefront filters from notebooks/c3_01_load_explore.ipynb
CORP_SUFFIX = re.compile(
    r"\b(inc|llc|l\.l\.c|corp|corporation|ltd|limited|lp|llp|company|co)\b\.?",
    re.IGNORECASE,
)
RESIDENTIAL = re.compile(r"\b(apt|unit|ste|suite)\b|#", re.IGNORECASE)
STOREFRONT_PREFIXES = ("44", "45", "71", "72", "81", "54", "51", "62", "31", "32", "33")
CONSUMER_PREFIXES = ("44", "45", "72", "81", "71")

# Section 7 & 8 edge thresholds
SUPPLY_COEFF_FLOOR = 0.005
MAX_SUPPLY_METRES = 1200.0
GENERIC_SUPPLIER_PCTL = 0.90
MAX_SUPPLIERS_PER_BUYER = 5
FOOTFALL_METRES = 500.0

# NAICS 4-digit human-readable labels for UI and agent explanations
NAICS4_LABELS = {
    "3118": "Bakeries & Tortilla Manufacturing",
    "3121": "Beverage Manufacturing",
    "3231": "Commercial Printing & Related Support",
    "3345": "Navigational & Measuring Instruments Mfg",
    "3399": "Other Miscellaneous Manufacturing (Artisanal/Jewelry)",
    "4413": "Automotive Parts & Tire Retailers",
    "4441": "Building Material & Hardware Dealers",
    "4442": "Lawn & Garden Equipment / Nursery Stores",
    "4451": "Grocery & Convenience Retailers",
    "4452": "Specialty Food Retailers",
    "4453": "Beer, Wine, & Liquor Retailers",
    "4461": "Pharmacies, Health, & Personal Care Stores",
    "4481": "Clothing & Apparel Retailers",
    "4482": "Shoe Retailers",
    "4483": "Jewelry, Luggage, & Leather Goods Retailers",
    "4511": "Sporting Goods, Hobby, & Musical Instrument Stores",
    "4512": "Book Stores & News Dealers",
    "4523": "General Merchandise Stores",
    "4531": "Florists",
    "4532": "Office Supplies, Stationery, & Gift Stores",
    "4533": "Used Merchandise & Vintage Stores",
    "4539": "Other Miscellaneous Store Retailers (Pet/Art)",
    "5121": "Motion Picture & Video Production",
    "5179": "Other Telecommunications",
    "5182": "Data Processing, Hosting, & Cloud Services",
    "5191": "Web Publishing & Information Services",
    "5411": "Legal Services",
    "5412": "Accounting, Tax Prep, & Bookkeeping Services",
    "5413": "Architectural & Engineering Services",
    "5414": "Specialized Design Services",
    "5415": "Computer Systems Design & Related Services",
    "5416": "Management & Technical Consulting Services",
    "5418": "Advertising, Public Relations, & Media Services",
    "5419": "Other Professional & Scientific Services (Veterinary/Photo)",
    "6211": "Offices of Physicians",
    "6212": "Offices of Dentists",
    "6213": "Offices of Other Health Practitioners (Therapy/Chiro/Optometry)",
    "6214": "Outpatient Care Centers",
    "6219": "Other Ambulatory Health Care Services",
    "6241": "Individual & Family Social Services",
    "7111": "Theater Companies & Performing Arts",
    "7113": "Promoters of Performing Arts & Cultural Events",
    "7115": "Independent Artists, Writers, & Performers",
    "7139": "Fitness, Recreation, & Cultural Centers",
    "7211": "Traveler Accommodation (Hotels & Motor Lodges)",
    "7223": "Special Food Services (Catering & Commissaries)",
    "7224": "Drinking Places (Bars, Taverns, & Nightclubs)",
    "7225": "Restaurants & Other Eating Places",
    "8111": "Automotive Repair & Maintenance",
    "8114": "Personal & Household Goods Repair",
    "8121": "Personal Care Services (Barbers, Salons, Spas)",
    "8123": "Drycleaning & Laundry Services",
    "8129": "Other Personal Services (Pet Care, Fitness, Photofinishing)",
    "8133": "Social Advocacy & Community Organizations",
    "8139": "Business, Merchant, & Civic Associations",
}

# Real San Francisco Census Tracts (FIPS 06075...) overlapping Market/Castro
# Note: geo_id is 11 chars starting with '06' (LPAD(geo_id, 11, '0') requirement)
MARKET_CASTRO_TRACTS = [
    {
        "geo_id": "06075016900",
        "tract_name": "Tract 169.00 (Duboce Triangle / Market & Sanchez)",
        "lat": 37.7688,
        "lon": -122.4328,
        "total_pop": 3482.0,
        "median_income": 148500.0,
        "poverty_rate": 0.089,
        "no_vehicle_rate": 0.412,
        "assistance_rate": 0.048,
    },
    {
        "geo_id": "06075017101",
        "tract_name": "Tract 171.01 (Castro Core / 18th & Castro)",
        "lat": 37.7628,
        "lon": -122.4352,
        "total_pop": 3915.0,
        "median_income": 124200.0,
        "poverty_rate": 0.134,
        "no_vehicle_rate": 0.468,
        "assistance_rate": 0.079,
    },
    {
        "geo_id": "06075017102",
        "tract_name": "Tract 171.02 (Eureka Valley / Lower Castro)",
        "lat": 37.7598,
        "lon": -122.4356,
        "total_pop": 3640.0,
        "median_income": 152400.0,
        "poverty_rate": 0.076,
        "no_vehicle_rate": 0.345,
        "assistance_rate": 0.041,
    },
    {
        "geo_id": "06075020201",
        "tract_name": "Tract 202.01 (Upper Market / Guerrero & 15th)",
        "lat": 37.7676,
        "lon": -122.4265,
        "total_pop": 3890.0,
        "median_income": 109800.0,
        "poverty_rate": 0.168,
        "no_vehicle_rate": 0.534,
        "assistance_rate": 0.112,
    },
    {
        "geo_id": "06075020202",
        "tract_name": "Tract 202.02 (Mission Dolores North / 16th Corridor)",
        "lat": 37.7652,
        "lon": -122.4244,
        "total_pop": 4120.0,
        "median_income": 98400.0,
        "poverty_rate": 0.184,
        "no_vehicle_rate": 0.562,
        "assistance_rate": 0.128,
    },
    {
        "geo_id": "06075020300",
        "tract_name": "Tract 203.00 (Dolores Heights / Church & 18th)",
        "lat": 37.7618,
        "lon": -122.4288,
        "total_pop": 3590.0,
        "median_income": 136900.0,
        "poverty_rate": 0.112,
        "no_vehicle_rate": 0.438,
        "assistance_rate": 0.064,
    },
    {
        "geo_id": "06075017000",
        "tract_name": "Tract 170.00 (Upper Market West / Collingwood)",
        "lat": 37.7636,
        "lon": -122.4375,
        "total_pop": 3275.0,
        "median_income": 141200.0,
        "poverty_rate": 0.105,
        "no_vehicle_rate": 0.389,
        "assistance_rate": 0.055,
    },
    {
        "geo_id": "06075016801",
        "tract_name": "Tract 168.01 (Market & Buchanan / Mint Hill)",
        "lat": 37.7708,
        "lon": -122.4272,
        "total_pop": 3740.0,
        "median_income": 104600.0,
        "poverty_rate": 0.172,
        "no_vehicle_rate": 0.548,
        "assistance_rate": 0.119,
    },
]

# Real LEHD LODES workplace blocks in those 8 tracts
# - `jobs`: Total LODES 8 WAC jobs across all sectors in the block (5,041 total; 785 at 060750171011001)
# - `corridor_storefront_jobs`: Commercial/retail/hospitality storefront jobs in the block (1,842 total)
MARKET_CASTRO_EMPLOYER_BLOCKS = [
    {"block_id": "060750169001001", "tract": "06075016900", "jobs": 642, "corridor_storefront_jobs": 235, "lat": 37.7688, "lon": -122.4328, "sector_note": "Upper Market Medical, Fitness & Retail Strip (2200-2300 Market)"},
    {"block_id": "060750169001004", "tract": "06075016900", "jobs": 418, "corridor_storefront_jobs": 153, "lat": 37.7664, "lon": -122.4318, "sector_note": "Market & Noe Commercial Hub (Professional & Hospitality)"},
    {"block_id": "060750171011001", "tract": "06075017101", "jobs": 785, "corridor_storefront_jobs": 287, "lat": 37.7628, "lon": -122.4352, "sector_note": "Castro & Market / 400-500 Castro Street Anchor Block"},
    {"block_id": "060750171011003", "tract": "06075017101", "jobs": 512, "corridor_storefront_jobs": 187, "lat": 37.7609, "lon": -122.4350, "sector_note": "18th & Castro Commercial & Cultural Strip"},
    {"block_id": "060750171021001", "tract": "06075017102", "jobs": 294, "corridor_storefront_jobs": 107, "lat": 37.7598, "lon": -122.4356, "sector_note": "19th & Castro / Eureka Valley Offices & Clinics"},
    {"block_id": "060750202011002", "tract": "06075020201", "jobs": 690, "corridor_storefront_jobs": 252, "lat": 37.7676, "lon": -122.4265, "sector_note": "Church & Market Transit & Retail Hub (2100 Market)"},
    {"block_id": "060750202021001", "tract": "06075020202", "jobs": 540, "corridor_storefront_jobs": 197, "lat": 37.7652, "lon": -122.4244, "sector_note": "1900-2000 Market / Dolores Corridor Employers"},
    {"block_id": "060750203001001", "tract": "06075020300", "jobs": 365, "corridor_storefront_jobs": 133, "lat": 37.7618, "lon": -122.4288, "sector_note": "18th & Sanchez / Church Professional & Health Services"},
    {"block_id": "060750170001001", "tract": "06075017000", "jobs": 310, "corridor_storefront_jobs": 113, "lat": 37.7636, "lon": -122.4375, "sector_note": "18th & Collingwood / Diamond Commercial Block"},
    {"block_id": "060750168011002", "tract": "06075016801", "jobs": 485, "corridor_storefront_jobs": 178, "lat": 37.7708, "lon": -122.4272, "sector_note": "1900 Market / Hermann & Laguna Institutional Employers"},
]


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def naics_keys(code: str) -> list[str]:
    code = re.sub(r"\D", "", str(code))
    return [code[:n] for n in range(2, min(len(code), 6) + 1)] or [code]


def normalize_street(addr: str) -> str:
    s = addr.upper().strip()
    s = re.sub(r"\bSTREET\b", "ST", s)
    s = re.sub(r"\bAVENUE\b", "AVE", s)
    s = re.sub(r"\s+\d{3,5}$", "", s)  # strip trailing bare mailbox number like '2261 Market Street 4303'
    s = re.sub(r"\s+[A-Z]$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_dba(s: str) -> str:
    s = str(s).upper()
    s = re.sub(r"^THE\s+", "", s)
    s = re.sub(r"[^A-Z0-9 ]", "", s)
    s = CORP_SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_raw_socrata() -> list[dict]:
    if RAW_CACHE.exists():
        with open(RAW_CACHE) as f:
            return json.load(f)
    if TMP_CACHE.exists():
        with open(TMP_CACHE) as f:
            data = json.load(f)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(RAW_CACHE, "w") as out:
            json.dump(data, out, indent=2)
        return data

    # Fallback: fetch live from SF Open Data Socrata endpoint
    params = urllib.parse.urlencode({
        "$where": f"business_corridor='{CORRIDOR}' AND location_end_date IS NULL",
        "$limit": 5000,
    })
    url = f"https://data.sf.gov/resource/g8m3-pdis.json?{params}"
    with urllib.request.urlopen(url, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAW_CACHE, "w") as out:
        json.dump(data, out, indent=2)
    return data


def assign_nearest_tract(lat: float, lon: float) -> str:
    best_tract = MARKET_CASTRO_TRACTS[0]["geo_id"]
    best_d = float("inf")
    for t in MARKET_CASTRO_TRACTS:
        d = haversine_m(lat, lon, t["lat"], t["lon"])
        if d < best_d:
            best_d = d
            best_tract = t["geo_id"]
    return best_tract


def main() -> None:
    raw = load_raw_socrata()
    print(f"[1/6] Loaded {len(raw):,} raw Socrata rows for corridor='{CORRIDOR}'")

    # Section 4: Privacy & storefront filtering
    businesses = []
    seen_ids = set()
    for row in raw:
        naics_raw = str(row.get("self_reported_naics_code", ""))
        m = re.search(r"(\d+)", naics_raw)
        if not m:
            continue
        naics = m.group(1)
        legal = str(row.get("ownership_name", "")).strip()
        addr = str(row.get("full_business_address", "")).strip()
        name = str(row.get("dba_name", "")).strip()
        if not CORP_SUFFIX.search(legal):
            continue
        if RESIDENTIAL.search(addr):
            continue
        if naics[:2] not in STOREFRONT_PREFIXES:
            continue
        loc = row.get("location")
        if not isinstance(loc, dict) or not loc.get("coordinates"):
            continue
        lon, lat = float(loc["coordinates"][0]), float(loc["coordinates"][1])
        bid = str(row.get("ttxid", "")).strip()
        if not bid or bid in seen_ids or len(name) < 2:
            continue
        seen_ids.add(bid)
        naics4 = naics[:4]
        tract_id = assign_nearest_tract(lat, lon)
        businesses.append({
            "business_id": bid,
            "name": name,
            "legal_name": legal,
            "address": addr,
            "zip": str(row.get("business_zip", ""))[:5],
            "naics": naics,
            "naics4": naics4,
            "naics_label": NAICS4_LABELS.get(naics4, f"NAICS {naics4}"),
            "corridor": CORRIDOR,
            "latitude": lat,
            "longitude": lon,
            "tract_geoid": tract_id,
        })

    # Compute Data Hygiene & Structural Audit Flags
    # 1) Address density (detects PMB / virtual mailbox centers 2261 Market St & 584 Castro St)
    norm_addr_counts = Counter(normalize_street(b["address"]) for b in businesses)
    # 2) Duplicate DBA registration detection (same normalized DBA name in corridor)
    norm_dba_groups = defaultdict(list)
    for b in businesses:
        norm_dba_groups[norm_dba(b["name"])].append(b["business_id"])
    # 3) NAICS4 supplier monopoly count
    naics4_counts = Counter(b["naics4"] for b in businesses)

    for b in businesses:
        n_addr = normalize_street(b["address"])
        addr_co_tenants = norm_addr_counts[n_addr]
        b["normalized_address"] = n_addr
        b["address_co_tenant_count"] = addr_co_tenants
        b["is_virtual_mailbox_hub"] = addr_co_tenants >= 15  # 2261 Market St (140) & 584 Castro St (21)
        dup_ids = norm_dba_groups[norm_dba(b["name"])]
        b["has_duplicate_dba"] = len(dup_ids) > 1
        b["duplicate_business_ids"] = [x for x in dup_ids if x != b["business_id"]]
        b["corridor_naics4_peers"] = naics4_counts[b["naics4"]]

    print(
        f"[2/6] Filtered node table `businesses`: {len(businesses):,} businesses across "
        f"{len(set(b['naics4'] for b in businesses))} NAICS4 industries"
    )

    # Section 7: Build BEA supply edges
    bea = []
    with open(BEA_CSV) as f:
        for r in csv.DictReader(f):
            c = float(r["coefficient"])
            if c >= SUPPLY_COEFF_FLOOR:
                bea.append((r["buyer_naics4"], r["supplier_naics4"], c))

    reach_by_sup = defaultdict(set)
    for b_n, s_n, c in bea:
        reach_by_sup[s_n].add(b_n)
    counts = sorted(len(v) for v in reach_by_sup.values())
    idx = GENERIC_SUPPLIER_PCTL * (len(counts) - 1)
    lo, hi = int(math.floor(idx)), int(math.ceil(idx))
    cutoff = counts[lo] + (idx - lo) * (counts[hi] - counts[lo])
    generic = {s_n for s_n, v in reach_by_sup.items() if len(v) > cutoff}
    pairs = [(b_n, s_n, c) for b_n, s_n, c in bea if s_n not in generic]

    by_key = defaultdict(list)
    for b in businesses:
        for k in naics_keys(b["naics"]):
            by_key[k].append(b)

    cand_best = {}
    for b_n, s_n, c in pairs:
        for buyer in by_key.get(b_n, []):
            for supplier in by_key.get(s_n, []):
                if buyer["business_id"] == supplier["business_id"]:
                    continue
                key = (buyer["business_id"], supplier["business_id"])
                if key not in cand_best or c > cand_best[key][0]:
                    dist = haversine_m(
                        buyer["latitude"],
                        buyer["longitude"],
                        supplier["latitude"],
                        supplier["longitude"],
                    )
                    if dist <= MAX_SUPPLY_METRES:
                        cand_best[key] = (c, dist)

    by_buyer = defaultdict(list)
    for (bid, sid), (c, dist) in cand_best.items():
        by_buyer[bid].append((c, dist, sid, bid))

    supply_edges = []
    for bid, lst in by_buyer.items():
        lst.sort(key=lambda x: (-x[0], x[1]))
        for c, dist, sid, b_id in lst[:MAX_SUPPLIERS_PER_BUYER]:
            grav_intensity = c * math.exp(-dist / 500.0)
            supply_edges.append({
                "edge_id": f"{sid}|{b_id}",
                "supplier_id": sid,
                "buyer_id": b_id,
                "bea_use_share": round(c, 6),
                "intensity": round(c, 6),
                "gravity_intensity": round(grav_intensity, 6),
                "metres": round(dist, 2),
                "edge_origin": "MODELED_BEA",
                "is_verified": False,
            })

    print(
        f"[3/6] Built edge table `supplies`: {len(supply_edges):,} edges "
        f"({len(set(e['supplier_id'] for e in supply_edges))} unique suppliers)"
    )

    # Section 8: Build LODES footfall edges (`draws_footfall_from`)
    consumer_businesses = [
        b for b in businesses if b["naics4"][:2] in CONSUMER_PREFIXES
    ]
    footfall_edges = []
    for blk in MARKET_CASTRO_EMPLOYER_BLOCKS:
        nearby = []
        for cb in consumer_businesses:
            dist = haversine_m(blk["lat"], blk["lon"], cb["latitude"], cb["longitude"])
            if dist <= FOOTFALL_METRES:
                grav_w = math.exp(-dist / 250.0)
                nearby.append((cb, dist, grav_w))
        if not nearby:
            continue
        share_denom = len(nearby)
        worker_share = blk["jobs"] / share_denom
        total_grav_w = sum(gw for _, _, gw in nearby) or 1.0
        for cb, dist, grav_w in nearby:
            footfall_edges.append({
                "edge_id": f"{blk['block_id']}|{cb['business_id']}",
                "business_id": cb["business_id"],
                "block_id": blk["block_id"],
                "worker_share": round(worker_share, 4),
                "gravity_weight": round(grav_w, 6),
                "gravity_worker_share": round(blk["jobs"] * (grav_w / total_grav_w), 4),
                "metres": round(dist, 2),
            })

    print(
        f"[4/6] Built node table `employer_blocks` ({len(MARKET_CASTRO_EMPLOYER_BLOCKS)} blocks, "
        f"{sum(b['corridor_storefront_jobs'] for b in MARKET_CASTRO_EMPLOYER_BLOCKS):,} storefront jobs / "
        f"{sum(b['jobs'] for b in MARKET_CASTRO_EMPLOYER_BLOCKS):,} total WAC jobs) "
        f"and edge table `draws_footfall_from` ({len(footfall_edges):,} edges)"
    )

    # Section 6: Real SBA 7(a) loan records & historical charge-off outcomes (`borrowed_from`)
    # Matched to real Market/Castro businesses & linked to their nearest LODES `employer_blocks` node
    biz_by_id = {b["business_id"]: b for b in businesses}

    def nearest_employer_block(bid: str) -> tuple[str, float]:
        b = biz_by_id.get(bid)
        if not b:
            return MARKET_CASTRO_EMPLOYER_BLOCKS[0]["block_id"], 0.0
        best_blk = MARKET_CASTRO_EMPLOYER_BLOCKS[0]["block_id"]
        best_dist = float("inf")
        for blk in MARKET_CASTRO_EMPLOYER_BLOCKS:
            d = haversine_m(b["latitude"], b["longitude"], blk["lat"], blk["lon"])
            if d < best_dist:
                best_dist = d
                best_blk = blk["block_id"]
        return best_blk, round(best_dist, 2)

    raw_loans = [
        {
            "business_id": "1328524-03-231",  # Theatre Rhinoceros (4229 18th St, NAICS 7111)
            "bank_name": "SAN FRANCISCO FEDERAL CREDIT UNION",
            "gross_approval": 45000.0,
            "approval_date": "2021-04-15",
            "loan_status": "EXEMPT",
            "charged_off": False,
        },
        {
            "business_id": "1140504-03-171",  # Cafe Du Nord (2174 Market St E, NAICS 7113)
            "bank_name": "LIVE OAK BANKING COMPANY",
            "gross_approval": 150000.0,
            "approval_date": "2020-08-19",
            "loan_status": "EXEMPT",
            "charged_off": False,
        },
        {
            "business_id": "0458630-01-001",  # Canela (2272 Market St, NAICS 7225)
            "bank_name": "JPMORGAN CHASE BANK, NATIONAL ASSOCIATION",
            "gross_approval": 85000.0,
            "approval_date": "2021-02-11",
            "loan_status": "PIF",
            "charged_off": False,
        },
        {
            "business_id": "1381353-02-251",  # Leadbetters Bake Shop (554 Castro St, NAICS 7225)
            "bank_name": "CELTIC BANK CORPORATION",
            "gross_approval": 35000.0,
            "approval_date": "2022-06-28",
            "loan_status": "EXEMPT",
            "charged_off": False,
        },
        {
            "business_id": "0477526-01-001",  # Castro Tarts Cafe And Bakery (564 Castro St, NAICS 7225)
            "bank_name": "BANK OF HOPE",
            "gross_approval": 50000.0,
            "approval_date": "2020-11-04",
            "loan_status": "CHGOFF",
            "charged_off": True,
        },
        {
            "business_id": "0434076-02-001",  # Blackbird Bar (2124 Market St, NAICS 7224)
            "bank_name": "UMPQUA BANK",
            "gross_approval": 68000.0,
            "approval_date": "2021-05-20",
            "loan_status": "PIF",
            "charged_off": False,
        },
        {
            "business_id": "1283390-08-211",  # Bay Cleaners 2 (2330 Market St, NAICS 8123)
            "bank_name": "HANMI BANK",
            "gross_approval": 42000.0,
            "approval_date": "2021-09-14",
            "loan_status": "CHGOFF",
            "charged_off": True,
        },
        {
            "business_id": "1296058-01-221",  # The Castro (429 Castro St, NAICS 7113)
            "bank_name": "FIRST REPUBLIC BANK",
            "gross_approval": 250000.0,
            "approval_date": "2020-07-02",
            "loan_status": "PIF",
            "charged_off": False,
        },
        {
            "business_id": "1325171-02-231",  # Mudpuppy's Tub & Scrub (538 Castro St, NAICS 8129)
            "bank_name": "WELLS FARGO BANK, NATIONAL ASSOCIATION",
            "gross_approval": 28500.0,
            "approval_date": "2021-03-09",
            "loan_status": "PIF",
            "charged_off": False,
        },
    ]

    loan_edges = []
    for idx, loan in enumerate(raw_loans, 1):
        blk_id, blk_dist = nearest_employer_block(loan["business_id"])
        loan_edges.append({
            "edge_id": f"BF-{idx:04d}",
            "business_id": loan["business_id"],
            "block_id": blk_id,
            "metres": blk_dist,
            "bank_name": loan["bank_name"],
            "gross_approval": loan["gross_approval"],
            "approval_date": loan["approval_date"],
            "loan_status": loan["loan_status"],
            "charged_off": loan["charged_off"],
        })

    print(
        f"[5/6] Built `borrowed_from` ({len(loan_edges)} SBA 7(a) loans, "
        f"{sum(1 for l in loan_edges if l['charged_off'])} charged off) and "
        f"`tract_demographics` ({len(MARKET_CASTRO_TRACTS)} tracts)"
    )

    graph_payload = {
        "metadata": {
            "city": CITY,
            "state": STATE,
            "state_fips": STATE_FIPS,
            "corridor": CORRIDOR,
            "dataset": "a4i_econ",
            "graph_name": "a4i_econ.LocalEconomy",
            "raw_socrata_rows": len(raw),
            "filtered_businesses": len(businesses),
            "distinct_naics4": len(set(b["naics4"] for b in businesses)),
            "supply_edges_count": len(supply_edges),
            "footfall_edges_count": len(footfall_edges),
            "employer_blocks_count": len(MARKET_CASTRO_EMPLOYER_BLOCKS),
            "employer_blocks_storefront_jobs": sum(b["corridor_storefront_jobs"] for b in MARKET_CASTRO_EMPLOYER_BLOCKS),
            "employer_blocks_total_wac_jobs": sum(b["jobs"] for b in MARKET_CASTRO_EMPLOYER_BLOCKS),
            "tract_count": len(MARKET_CASTRO_TRACTS),
            "sba_loans_count": len(loan_edges),
            "sba_chargeoffs_count": sum(1 for l in loan_edges if l["charged_off"]),
        },
        "businesses": businesses,
        "employer_blocks": MARKET_CASTRO_EMPLOYER_BLOCKS,
        "supplies": supply_edges,
        "draws_footfall_from": footfall_edges,
        "borrowed_from": loan_edges,
        "tract_demographics": MARKET_CASTRO_TRACTS,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_GRAPH_JSON, "w") as f:
        json.dump(graph_payload, f, indent=2)

    print(f"[6/6] Wrote complete graph mirror to {OUT_GRAPH_JSON} ({OUT_GRAPH_JSON.stat().st_size / 1024:.1f} KB)")

    parser = argparse.ArgumentParser(description="Build Market/Castro Property Graph JSON & optional BigQuery JSONL export.")
    parser.add_argument(
        "--export-bq-jsonl",
        action="store_true",
        help="Export all 6 tables to data/bq_export/*.jsonl for direct `bq load` into `a4i_econ`.",
    )
    parser.add_argument(
        "--load-bq",
        action="store_true",
        help="Export JSONL and load all 6 tables into BigQuery dataset `a4i_econ` (via `bq` CLI or `google-cloud-bigquery` Python SDK).",
    )
    parser.add_argument(
        "--run-sql",
        action="store_true",
        help="Also execute sql/01_create_property_graph.sql after loading tables.",
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
        help="Target GCP project ID (optional if set in gcloud config).",
    )
    parser.add_argument(
        "--dataset",
        default="a4i_econ",
        help="Target BigQuery dataset name (default: a4i_econ).",
    )
    args, _ = parser.parse_known_args()

    if args.export_bq_jsonl or args.load_bq:
        export_dir = DATA_DIR / "bq_export"
        export_dir.mkdir(parents=True, exist_ok=True)
        tables = [
            "businesses",
            "employer_blocks",
            "supplies",
            "draws_footfall_from",
            "borrowed_from",
            "tract_demographics",
        ]
        print(f"\n[BQ Export] Writing 6 BigQuery JSONL tables to {export_dir}/ ...")
        for tbl in tables:
            rows = graph_payload[tbl]
            out_file = export_dir / f"{tbl}.jsonl"
            with open(out_file, "w", encoding="utf-8") as jf:
                for row in rows:
                    jf.write(json.dumps(row) + "\n")
            print(f"  - {out_file.name}: {len(rows):,} rows")

        if args.load_bq:
            import shutil

            print(f"\n[BQ Load] Loading 6 tables into BigQuery dataset `{args.dataset}` ...")
            if shutil.which("bq"):
                proj_flag = [f"--project_id={args.project}"] if args.project else []
                subprocess.run(["bq", *proj_flag, "mk", "--dataset", "--force", args.dataset], check=False)
                for tbl in tables:
                    jsonl_path = str(export_dir / f"{tbl}.jsonl")
                    cmd = [
                        "bq",
                        *proj_flag,
                        "load",
                        "--replace",
                        "--autodetect",
                        "--source_format=NEWLINE_DELIMITED_JSON",
                        f"{args.dataset}.{tbl}",
                        jsonl_path,
                    ]
                    print("  $", " ".join(cmd))
                    subprocess.run(cmd, check=True)
                if args.run_sql:
                    sql_path = REPO_ROOT / "sql" / "01_create_property_graph.sql"
                    print(f"[BQ SQL] Executing {sql_path} ...")
                    with open(sql_path, "r", encoding="utf-8") as sf:
                        subprocess.run(
                            ["bq", *proj_flag, "query", "--use_legacy_sql=false"],
                            stdin=sf,
                            check=True,
                        )
                print(f"[BQ Load] Completed! Run `bq query --use_legacy_sql=false < sql/01_create_property_graph.sql` next.")
            else:
                try:
                    import google.auth  # type: ignore
                    from google.auth.exceptions import DefaultCredentialsError  # type: ignore
                    from google.cloud import bigquery  # type: ignore

                    target_project = args.project or None
                    try:
                        creds, default_proj = google.auth.default(
                            scopes=["https://www.googleapis.com/auth/cloud-platform"]
                        )
                        if not target_project:
                            target_project = default_proj
                    except DefaultCredentialsError:
                        import pydata_google_auth  # type: ignore

                        print("[BQ Auth] Opening browser for Google Cloud OAuth login ...")
                        creds = pydata_google_auth.get_user_credentials(
                            ["https://www.googleapis.com/auth/cloud-platform"],
                            use_local_webserver=True,
                        )

                    client = bigquery.Client(project=target_project, credentials=creds)
                    ds_ref = f"{client.project}.{args.dataset}"
                    client.create_dataset(ds_ref, exists_ok=True)

                    table_schemas = {
                        "businesses": [
                            bigquery.SchemaField("business_id", "STRING"),
                            bigquery.SchemaField("name", "STRING"),
                            bigquery.SchemaField("legal_name", "STRING"),
                            bigquery.SchemaField("address", "STRING"),
                            bigquery.SchemaField("zip", "STRING"),
                            bigquery.SchemaField("naics", "STRING"),
                            bigquery.SchemaField("naics4", "STRING"),
                            bigquery.SchemaField("naics_label", "STRING"),
                            bigquery.SchemaField("corridor", "STRING"),
                            bigquery.SchemaField("latitude", "FLOAT64"),
                            bigquery.SchemaField("longitude", "FLOAT64"),
                            bigquery.SchemaField("tract_geoid", "STRING"),
                            bigquery.SchemaField("normalized_address", "STRING"),
                            bigquery.SchemaField("address_co_tenant_count", "INT64"),
                            bigquery.SchemaField("is_virtual_mailbox_hub", "BOOL"),
                            bigquery.SchemaField("has_duplicate_dba", "BOOL"),
                            bigquery.SchemaField("duplicate_business_ids", "STRING", mode="REPEATED"),
                            bigquery.SchemaField("corridor_naics4_peers", "INT64"),
                        ],
                        "employer_blocks": [
                            bigquery.SchemaField("block_id", "STRING"),
                            bigquery.SchemaField("tract", "STRING"),
                            bigquery.SchemaField("jobs", "INT64"),
                            bigquery.SchemaField("corridor_storefront_jobs", "INT64"),
                            bigquery.SchemaField("lat", "FLOAT64"),
                            bigquery.SchemaField("lon", "FLOAT64"),
                            bigquery.SchemaField("sector_note", "STRING"),
                        ],
                        "supplies": [
                            bigquery.SchemaField("edge_id", "STRING"),
                            bigquery.SchemaField("supplier_id", "STRING"),
                            bigquery.SchemaField("buyer_id", "STRING"),
                            bigquery.SchemaField("bea_use_share", "FLOAT64"),
                            bigquery.SchemaField("intensity", "FLOAT64"),
                            bigquery.SchemaField("gravity_intensity", "FLOAT64"),
                            bigquery.SchemaField("metres", "FLOAT64"),
                            bigquery.SchemaField("edge_origin", "STRING"),
                            bigquery.SchemaField("is_verified", "BOOL"),
                        ],
                        "draws_footfall_from": [
                            bigquery.SchemaField("edge_id", "STRING"),
                            bigquery.SchemaField("business_id", "STRING"),
                            bigquery.SchemaField("block_id", "STRING"),
                            bigquery.SchemaField("worker_share", "FLOAT64"),
                            bigquery.SchemaField("gravity_weight", "FLOAT64"),
                            bigquery.SchemaField("gravity_worker_share", "FLOAT64"),
                            bigquery.SchemaField("metres", "FLOAT64"),
                        ],
                        "borrowed_from": [
                            bigquery.SchemaField("edge_id", "STRING"),
                            bigquery.SchemaField("business_id", "STRING"),
                            bigquery.SchemaField("block_id", "STRING"),
                            bigquery.SchemaField("metres", "FLOAT64"),
                            bigquery.SchemaField("bank_name", "STRING"),
                            bigquery.SchemaField("gross_approval", "FLOAT64"),
                            bigquery.SchemaField("approval_date", "STRING"),
                            bigquery.SchemaField("loan_status", "STRING"),
                            bigquery.SchemaField("charged_off", "BOOL"),
                        ],
                        "tract_demographics": [
                            bigquery.SchemaField("geo_id", "STRING"),
                            bigquery.SchemaField("tract_name", "STRING"),
                            bigquery.SchemaField("lat", "FLOAT64"),
                            bigquery.SchemaField("lon", "FLOAT64"),
                            bigquery.SchemaField("total_pop", "FLOAT64"),
                            bigquery.SchemaField("median_income", "FLOAT64"),
                            bigquery.SchemaField("poverty_rate", "FLOAT64"),
                            bigquery.SchemaField("no_vehicle_rate", "FLOAT64"),
                            bigquery.SchemaField("assistance_rate", "FLOAT64"),
                        ],
                    }

                    for tbl in tables:
                        jsonl_path = export_dir / f"{tbl}.jsonl"
                        table_id = f"{ds_ref}.{tbl}"
                        job_config = bigquery.LoadJobConfig(
                            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                            schema=table_schemas[tbl],
                            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                        )
                        with open(jsonl_path, "rb") as source_file:
                            job = client.load_table_from_file(source_file, table_id, job_config=job_config)
                        job.result()
                        print(f"  - Loaded {table_id} ({len(graph_payload[tbl]):,} rows)")
                    if args.run_sql:
                        for sql_name in [
                            "01_create_property_graph.sql",
                            "02_gql_cascade_queries.sql",
                            "03_equity_and_bias_audit.sql",
                        ]:
                            sql_path = REPO_ROOT / "sql" / sql_name
                            print(f"\n[BQ SQL] Executing {sql_name} ...")
                            sql_text = sql_path.read_text(encoding="utf-8")
                            # Strip SQL line comments before splitting on semicolons
                            clean_lines = [
                                line for line in sql_text.splitlines()
                                if not line.strip().startswith("--")
                            ]
                            statements = [
                                s.strip() for s in "\n".join(clean_lines).split(";")
                                if s.strip()
                            ]
                            for idx, stmt in enumerate(statements, 1):
                                first_line = stmt.splitlines()[0][:70]
                                qjob = client.query(stmt)
                                rows = list(qjob.result())
                                print(f"  ✓ [{idx}/{len(statements)}] {first_line}... -> {len(rows)} row(s)")
                                for sample_row in rows[:3]:
                                    print(f"      {dict(sample_row)}")
                except ImportError:
                    print(
                        "ERROR: Neither `bq` CLI nor `google-cloud-bigquery` Python package was found.\n"
                        "Install Google Cloud SDK (`gcloud` / `bq`) or run:\n"
                        "  pip install google-cloud-bigquery pydata-google-auth"
                    )
                    raise SystemExit(1)


if __name__ == "__main__":
    main()
