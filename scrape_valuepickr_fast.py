"""
Scrape ValuePickr forum: N-day message counts aggregated by industry.
Optimized with concurrent requests + rate limiting.

Usage:
  python scrape_valuepickr_fast.py           # default 90 days
  python scrape_valuepickr_fast.py --days 30 # last 30 days
"""
import requests
import time
import json
import argparse
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://forum.valuepickr.com"
REPO = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
MAX_WORKERS = 5
STOCK_CATEGORY_IDS = {11, 14, 18, 19, 21, 69}

# Rate limiter: allow max 5 requests per second across all threads
_rate_lock = threading.Lock()
_last_request_time = 0.0

def rate_limited_get(url, timeout=15):
    """Thread-safe rate-limited GET with retry."""
    global _last_request_time
    for attempt in range(3):
        with _rate_lock:
            now = time.time()
            wait = max(0, 0.2 - (now - _last_request_time))  # 200ms between requests
            if wait > 0:
                time.sleep(wait)
            _last_request_time = time.time()
        try:
            resp = requests.get(url, headers={"Accept": "application/json"}, timeout=timeout)
            if resp.status_code == 429:  # Rate limited
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException:
            if attempt < 2:
                time.sleep(1)
            continue
    return None

# ── Industry mapping ──────────────────────────────────────────────────
MANUAL_INDUSTRY = {
    "IDFC First Bank": "Banks", "Bandhan Bank": "Banks",
    "Tamilnad Mercantile Bank": "Banks", "Equitas Small Finance Bank": "Banks",
    "CSB BANK": "Banks", "South Indian Bank": "Banks",
    "HDFC Bank": "Banks", "Ujjivan Small Finance Bank": "Banks",
    "E2E Networks": "IT - Software", "Zaggle": "IT - Software",
    "All E Technologies": "IT - Software", "Dynacons Systems": "IT - Software",
    "NPST": "IT - Software", "KPIT": "IT - Software",
    "Intellect Design Arena": "IT - Software", "Affle India": "IT - Software",
    "NetWeb Technologies": "IT - Software", "Ceinsys Tech": "IT - Software",
    "Genesys International": "IT - Software", "MPS Ltd": "IT - Software",
    "Info Edge": "IT - Software", "Mobikwik": "IT - Software",
    "ASM Technologies": "IT - Software", "EFC": "IT - Software",
    "Sagility India": "IT - Software", "Geospatial sector": "IT - Software",
    "Newgen Software": "IT - Software", "Veefin Solutions": "IT - Software",
    "Ola Electric": "Electric Vehicles",
    "Waaree Energies": "Solar Energy", "Vikram Solar": "Solar Energy",
    "HBL Engineering": "Electronics", "Kaynes Technology": "Electronics",
    "Shivalik Bimetal": "Electronics", "Semiconductor": "Electronics",
    "Avalon Technologies": "Electronics", "Dixon Technologies": "Electronics",
    "Avanti Feeds": "Aquaculture", "Kings Infra": "Aquaculture",
    "MTAR Technologies": "Industrial Manufacturing", "Praj Industries": "Industrial Manufacturing",
    "Balu Forge": "Industrial Manufacturing", "CFF Fluid Control": "Industrial Manufacturing",
    "Permanent Magnets": "Industrial Manufacturing", "Inox India": "Industrial Manufacturing",
    "Elecon Engineering": "Industrial Manufacturing", "Aeroflex Industries": "Industrial Manufacturing",
    "Kalyani Cast-Tech": "Iron & Steel Products", "Steelcast": "Iron & Steel Products",
    "Gujarat Intrux": "Iron & Steel Products", "Krishca Ltd": "Iron & Steel Products",
    "Sambhv Steel": "Iron & Steel Products", "Maharashtra seamless": "Iron & Steel Products",
    "Surya roshni": "Iron & Steel Products",
    "Kiri Industries": "Dyes & Pigments",
    "BSE": "Exchange & Data Platform", "MCX": "Exchange & Data Platform",
    "Indian Energy Exchange": "Exchange & Data Platform",
    "CDSL": "Depositories & Intermediaries",
    "Manorama Industries": "Edible Oil", "BCL Industries": "Edible Oil",
    "Kovai Medical": "Hospitals & Diagnostics", "3B Blackbio DX": "Hospitals & Diagnostics",
    "Yatharth Hospital": "Hospitals & Diagnostics", "Shalby Hospitals": "Hospitals & Diagnostics",
    "Rainbow Children": "Hospitals & Diagnostics", "Dr Lal PathLabs": "Hospitals & Diagnostics",
    "Thyrocare": "Hospitals & Diagnostics", "Krsnaa Diagnostics": "Hospitals & Diagnostics",
    "Max Healthcare": "Hospitals & Diagnostics",
    "Muthoot Finance": "NBFC", "Muthoot Microfin": "NBFC",
    "Manappuram Finance": "NBFC", "Ugro Capital": "NBFC",
    "Aavas Financiers": "NBFC", "Edelweiss Financial": "NBFC",
    "Arman Financial": "NBFC", "Five Star Business Finance": "NBFC",
    "CreditAccess Grameen": "NBFC", "Piramal Finance": "NBFC",
    "Sammaan Capital": "NBFC",
    "Afcom Holdings": "Logistics", "Knowledge Marine": "Logistics",
    "Interarch": "Construction", "EMS Limited": "Construction",
    "SEPC LTD": "Construction", "H.G. Infra": "Construction",
    "South West Pinnacle": "Construction", "RBM Infra": "Construction",
    "EPACK PREFAB": "Construction", "Crizac": "Construction", "L&T": "Construction",
    "BLS International": "Outsourcing & Consulting",
    "Security and Intelligence": "Outsourcing & Consulting",
    "Quess Corp": "Outsourcing & Consulting",
    "CONNPLEX CINEMA": "Entertainment", "PVR": "Entertainment",
    "Concord Control Systems": "Railways", "Kernex": "Railways",
    "GPT Infra": "Railways",
    "Time Technoplast": "Plastic Products", "Tinna rubber": "Plastic Products",
    "Multibase India": "Plastic Products", "Dhabriya Polywood": "Plastic Products",
    "DDev Plastiks": "Plastic Products", "Accent Microcell": "Plastic Products",
    "CarTrade Tech": "Internet & Catalogue Retail", "Zomato": "Internet & Catalogue Retail",
    "Brainbees": "Internet & Catalogue Retail", "FirstCry": "Internet & Catalogue Retail",
    "Nykaa": "Internet & Catalogue Retail", "Macfos": "Internet & Catalogue Retail",
    "TBO Tek": "Internet & Catalogue Retail",
    "Anant Raj": "Real Estate", "Ashiana Housing": "Real Estate",
    "Arkade Developers": "Real Estate", "Kontor Space": "Real Estate",
    "Arihant Foundations": "Real Estate",
    "Deep Industries": "Oil & Gas", "JNK India": "Oil & Gas",
    "Natco Pharma": "Pharmaceuticals", "Supriya Lifescience": "Pharmaceuticals",
    "Kwality Pharmaceuticals": "Pharmaceuticals", "Windlas Biotech": "Pharmaceuticals",
    "Zydus Lifesciences": "Pharmaceuticals", "Aarti Pharma Labs": "Pharmaceuticals",
    "Dishman Carbogen": "Pharmaceuticals", "Cohance life science": "Pharmaceuticals",
    "Sai Life Sciences": "Pharmaceuticals", "Beta Drugs": "Pharmaceuticals",
    "Innova Captab": "Pharmaceuticals", "Neuland Laboratories": "Pharmaceuticals",
    "Shilpa Medicare": "Pharmaceuticals", "Kopran": "Pharmaceuticals",
    "Influx HealthTech": "Pharmaceuticals", "Senores Pharma": "Pharmaceuticals",
    "Sakar Healthcare": "Pharmaceuticals", "Cipla": "Pharmaceuticals",
    "Gravita India": "Non-Ferrous Metals", "Vedanta": "Non-Ferrous Metals",
    "Hindustan Zinc": "Non-Ferrous Metals", "MIDHANI": "Non-Ferrous Metals",
    "Bharti Airtel": "Telecom", "Valiant Communications": "Telecom",
    "Sterlite Technologies": "Telecom Cables",
    "TD Power Systems": "Heavy Electrical Equipment",
    "Shilchar Technologies": "Heavy Electrical Equipment",
    "Transformer & Rectifier": "Heavy Electrical Equipment",
    "Yash High Voltage": "Heavy Electrical Equipment",
    "Lumax Auto": "Auto Components", "Sandhar Technologies": "Auto Components",
    "GG Automotive": "Auto Components", "SJS Enterprises": "Auto Components",
    "Pricol": "Auto Components",
    "Hawkins Cookers": "Consumer Durables", "La Opala": "Consumer Durables",
    "Carysil": "Consumer Durables", "Shree Refrigerations": "Consumer Durables",
    "Timex Group": "Consumer Durables", "Empire Industries": "Consumer Durables",
    "Religare Enterprises": "Finance",
    "IGI India": "Diamond, Gems & Jewellery", "Goldiam International": "Diamond, Gems & Jewellery",
    "Titan Company": "Diamond, Gems & Jewellery",
    "Deccan Gold": "Mining & Mineral Products", "20 Microns": "Mining & Mineral Products",
    "Rare Earth": "Mining & Mineral Products", "Coal India": "Mining & Mineral Products",
    "Nuclear Energy": "Power Generation & Distribution",
    "Tata Power": "Power Generation & Distribution", "Skipper": "Power Generation & Distribution",
    "Krishna Defence": "Defence", "C2C Advanced Systems": "Defence",
    "Zen technologies": "Defence", "Hindustan Aeronautics": "Defence",
    "Rossell Techsys": "Defence",
    "Avenue Supermart": "Retailing", "Safe Enterprises": "Retailing",
    "Vinati Organics": "Specialty Chemicals", "Himadri Specialty": "Specialty Chemicals",
    "Kesar Petroproducts": "Specialty Chemicals", "Rossari Biotech": "Specialty Chemicals",
    "Styrenix": "Specialty Chemicals", "Stallion India Fluoro": "Specialty Chemicals",
    "Kaveri seeds": "Agrochemicals", "Sharda Cropchem": "Agrochemicals",
    "UPL": "Agrochemicals", "Insecticides India": "Agrochemicals",
    "Radico khaitan": "Alcoholic Beverages", "Piccadily Agro": "Alcoholic Beverages",
    "Marico": "FMCG", "Hatsun Agro": "FMCG", "KRBL": "FMCG",
    "Marico Kaya": "FMCG", "Nurture Well": "FMCG", "Varun beverages": "FMCG",
    "Borana Weaves": "Textiles", "Mayur Uniquoters": "Textiles",
    "Ambika Cotton": "Textiles",
    "Cybele Ind": "Cables",
    "ICICI Prudential": "Asset Management", "Canara Robeco AMC": "Asset Management",
    "Lemon Tree Hotels": "Hotels / Hospitality", "Kamat Hotels": "Hotels / Hospitality",
    "Burger King": "Hotels / Hospitality",
    "S Chand": "Media & Publishing",
    "Vintage Coffee": "Plantation & Plantation Products",
    "AGI Greenpac": "Packaging",
    "Force Motors": "Automobiles", "Bajaj Auto": "Automobiles",
    "Gandhar Oil": "Petrochemicals",
    "HDFC Life": "Life Insurance",
    "JSW Infrastructure": "Infrastructure",
    "3M India": "Diversified", "ADAG Group": "Diversified",
}


def fetch_all_topics(cutoff):
    """Fetch all topics with recent activity using /latest.json."""
    topics = []
    seen_ids = set()
    page = 0

    while True:
        url = f"{BASE_URL}/latest.json?page={page}&no_definitions=true"
        print(f"  page {page}...", end=" ", flush=True)
        resp = rate_limited_get(url)
        if not resp:
            break

        data = resp.json()
        topic_list = data.get("topic_list", {})
        page_topics = topic_list.get("topics", [])

        if not page_topics:
            break

        stopped_early = False
        for t in page_topics:
            tid = t["id"]
            if tid in seen_ids:
                continue
            seen_ids.add(tid)

            cat_id = t.get("category_id", 0)
            if cat_id not in STOCK_CATEGORY_IDS:
                continue

            last_posted = t.get("last_posted_at", "")
            if not last_posted:
                continue
            last_dt = datetime.fromisoformat(last_posted.replace("Z", "+00:00"))

            if last_dt < cutoff:
                stopped_early = True
                break

            if t.get("pinned", False):
                continue

            title = (t.get("fancy_title", t.get("title", ""))
                      .replace("&rsquo;", "'").replace("&amp;", "&")
                      .replace("&ndash;", "-"))

            topics.append({
                "id": tid, "title": title,
                "total_posts": t.get("posts_count", 0),
                "last_posted_at": last_posted,
                "views": t.get("views", 0),
                "like_count": t.get("like_count", 0),
                "category_id": cat_id,
            })

        if stopped_early or "more_topics_url" not in topic_list:
            break
        page += 1

    print()
    return topics


def count_recent_posts(topic_id, total_posts, cutoff):
    """Count posts in the last N days. Returns (topic_id, count)."""
    resp = rate_limited_get(f"{BASE_URL}/t/{topic_id}.json")
    if not resp:
        return (topic_id, 0)
    data = resp.json()

    post_stream = data.get("post_stream", {})
    all_post_ids = post_stream.get("stream", [])

    if not all_post_ids:
        return (topic_id, 0)

    # Small topics: all posts in initial response
    if total_posts <= 20:
        posts = post_stream.get("posts", [])
        count = sum(1 for p in posts
                    if p.get("created_at") and
                    datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")) >= cutoff)
        return (topic_id, count)

    # Large topics: fetch from the END working backwards
    recent_count = 0
    chunk_size = 20

    for start_idx in range(len(all_post_ids) - 1, -1, -chunk_size):
        end_idx = max(start_idx - chunk_size + 1, 0)
        chunk_ids = all_post_ids[end_idx:start_idx + 1]
        if not chunk_ids:
            break

        params = "&".join([f"post_ids[]={pid}" for pid in chunk_ids])
        resp = rate_limited_get(f"{BASE_URL}/t/{topic_id}/posts.json?{params}")
        if not resp:
            break

        found_old = False
        for p in resp.json().get("post_stream", {}).get("posts", []):
            created = p.get("created_at", "")
            if created:
                pdt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if pdt >= cutoff:
                    recent_count += 1
                else:
                    found_old = True

        if found_old:
            break

    return (topic_id, recent_count)


def map_to_industry(title):
    for key, industry in MANUAL_INDUSTRY.items():
        if key.lower() in title.lower():
            return industry
    return "Other / Unclassified"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90, help="Lookback period in days")
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    print("=" * 70)
    print(f"VALUEPICKR {args.days}-DAY INDUSTRY SENTIMENT (fast, {MAX_WORKERS} threads)")
    print(f"Cutoff: {cutoff.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)

    # Phase 1
    print("\n⏳ Phase 1: Fetching topics...", flush=True)
    t0 = time.time()
    topics = fetch_all_topics(cutoff)
    print(f"  → {len(topics)} stock topics ({time.time() - t0:.1f}s)")

    # Phase 2: parallel counting
    print(f"\n⏳ Phase 2: Counting posts ({MAX_WORKERS} threads)...")
    t1 = time.time()
    topic_map = {t["id"]: t for t in topics}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(count_recent_posts, t["id"], t["total_posts"], cutoff): t["id"]
            for t in topics
        }
        done_count = 0
        for future in as_completed(futures):
            tid, count = future.result()
            topic_map[tid]["recent_posts"] = count
            topic_map[tid]["industry"] = map_to_industry(topic_map[tid]["title"])
            done_count += 1
            if done_count % 50 == 0 or done_count == len(topics):
                print(f"  {done_count}/{len(topics)} done...", flush=True)

    elapsed = time.time() - t1
    print(f"  → Completed ({elapsed:.1f}s, {len(topics)/max(elapsed,0.1):.1f} topics/sec)")

    # Aggregate by industry
    industry_counts = defaultdict(lambda: {"posts": 0, "topics": 0, "companies": []})
    for t in topics:
        ind = t["industry"]
        posts = t.get("recent_posts", 0)
        if posts > 0:
            industry_counts[ind]["posts"] += posts
            industry_counts[ind]["topics"] += 1
            industry_counts[ind]["companies"].append((t["title"][:40], posts))

    sorted_industries = sorted(industry_counts.items(), key=lambda x: x[1]["posts"], reverse=True)

    # Display
    print("\n" + "=" * 90)
    print(f"{'Rank':<5} {'Industry':<40} {f'{args.days}d Posts':<10} {'Topics':<8} {'Top Company':<35}")
    print("=" * 90)
    for i, (ind, d) in enumerate(sorted_industries, 1):
        top = max(d["companies"], key=lambda x: x[1])[0] if d["companies"] else ""
        print(f"{i:<5} {ind[:38]:<40} {d['posts']:<10} {d['topics']:<8} {top[:33]:<35}")
    print("=" * 90)
    total_time = time.time() - t0
    print(f"\n✅ Total time: {total_time:.1f}s")

    # Save
    out = {
        "days": args.days, "cutoff": cutoff.isoformat(),
        "total_topics": len(topics),
        "industry_summary": {ind: {"total_posts": d["posts"], "topic_count": d["topics"],
                                    "companies": d["companies"]}
                             for ind, d in sorted_industries},
        "topics": topics
    }
    suffix = f"{args.days}d"
    out_path = REPO / f"valuepickr_{suffix}_industry_counts.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"Saved to: {out_path}")


if __name__ == "__main__":
    main()
