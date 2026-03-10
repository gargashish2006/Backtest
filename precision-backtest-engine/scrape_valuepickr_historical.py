"""
Historical ValuePickr Scraper — Fetch all per-post data from stock topics.

Usage:
  python scrape_valuepickr_historical.py --mode full    # First-time full scrape
  python scrape_valuepickr_historical.py --mode update  # Incremental update
"""
import requests
import time
import json
import argparse
import threading
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://forum.valuepickr.com"
REPO = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
OUT_PARQUET = REPO / "database" / "valuepickr_posts.parquet"
CHECKPOINT_FILE = REPO / "valuepickr_scrape_checkpoint.json"
MAX_WORKERS = 5
STOCK_CATEGORY_IDS = {11, 14, 18, 19, 21, 69}

# ── Rate limiter ──────────────────────────────────────────────────────
_rate_lock = threading.Lock()
_last_request_time = 0.0

def rate_limited_get(url, timeout=15):
    global _last_request_time
    for attempt in range(3):
        with _rate_lock:
            now = time.time()
            wait = max(0, 0.2 - (now - _last_request_time))
            if wait > 0:
                time.sleep(wait)
            _last_request_time = time.time()
        try:
            resp = requests.get(url, headers={"Accept": "application/json"}, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
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

def map_to_industry(title):
    for key, industry in MANUAL_INDUSTRY.items():
        if key.lower() in title.lower():
            return industry
    return "Other / Unclassified"


# ── Phase 1: Discover ALL stock topics ────────────────────────────────

def fetch_all_stock_topics():
    """Paginate /latest.json deeply to get ALL stock topics (including old ones)."""
    topics = []
    seen_ids = set()
    page = 0

    while True:
        url = f"{BASE_URL}/latest.json?page={page}&no_definitions=true"
        resp = rate_limited_get(url)
        if not resp:
            break

        data = resp.json()
        topic_list = data.get("topic_list", {})
        page_topics = topic_list.get("topics", [])

        if not page_topics:
            break

        for t in page_topics:
            tid = t["id"]
            if tid in seen_ids:
                continue
            seen_ids.add(tid)

            cat_id = t.get("category_id", 0)
            if cat_id not in STOCK_CATEGORY_IDS:
                continue

            if t.get("pinned", False):
                continue

            title = (t.get("fancy_title", t.get("title", ""))
                      .replace("&rsquo;", "'").replace("&amp;", "&")
                      .replace("&ndash;", "-"))

            topics.append({
                "id": tid,
                "title": title,
                "total_posts": t.get("posts_count", 0),
                "category_id": cat_id,
            })

        if "more_topics_url" not in topic_list:
            break

        page += 1
        if page % 10 == 0:
            print(f"    page {page} ({len(topics)} stock topics so far)...", flush=True)

    return topics


# ── Phase 2: Fetch all posts for a topic ──────────────────────────────

def fetch_topic_posts(topic_id, title, skip_post_ids=None):
    """Fetch ALL posts for a given topic. Returns list of post dicts."""
    skip_post_ids = skip_post_ids or set()

    # Get topic to retrieve full post stream
    resp = rate_limited_get(f"{BASE_URL}/t/{topic_id}.json")
    if not resp:
        return []

    data = resp.json()
    post_stream = data.get("post_stream", {})
    all_post_ids = post_stream.get("stream", [])
    initial_posts = post_stream.get("posts", [])

    if not all_post_ids:
        return []

    industry = map_to_industry(title)
    results = []

    # Process initial posts (first ~20)
    initial_ids_seen = set()
    for p in initial_posts:
        pid = p["id"]
        initial_ids_seen.add(pid)
        if pid in skip_post_ids:
            continue
        results.append(_extract_post(p, topic_id, title, industry))

    # Fetch remaining posts in chunks
    remaining_ids = [pid for pid in all_post_ids
                     if pid not in initial_ids_seen and pid not in skip_post_ids]

    for i in range(0, len(remaining_ids), 20):
        chunk = remaining_ids[i:i+20]
        params = "&".join([f"post_ids[]={pid}" for pid in chunk])
        resp = rate_limited_get(f"{BASE_URL}/t/{topic_id}/posts.json?{params}")
        if not resp:
            continue
        for p in resp.json().get("post_stream", {}).get("posts", []):
            if p["id"] not in skip_post_ids:
                results.append(_extract_post(p, topic_id, title, industry))

    return results


def _extract_post(post, topic_id, title, industry):
    return {
        "post_id": post["id"],
        "topic_id": topic_id,
        "topic_title": title,
        "industry": industry,
        "created_at": post.get("created_at", ""),
        "like_count": post.get("like_count", 0),
        "author": post.get("username", ""),
        "author_trust_level": post.get("trust_level", 0),
    }


# ── Checkpoint management ─────────────────────────────────────────────

def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"completed_topics": [], "all_posts": []}

def save_checkpoint(checkpoint):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f)

def clear_checkpoint():
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()


# ── Main ──────────────────────────────────────────────────────────────

def run_full_scrape():
    print("=" * 70)
    print("VALUEPICKR HISTORICAL SCRAPER — FULL MODE")
    print("=" * 70)

    # Load checkpoint for resume support
    ckpt = load_checkpoint()
    completed_set = set(ckpt["completed_topics"])
    all_posts = ckpt["all_posts"]

    if completed_set:
        print(f"\n🔄 Resuming from checkpoint: {len(completed_set)} topics already done, "
              f"{len(all_posts)} posts collected.\n")

    # Phase 1: Discover topics
    print("⏳ Phase 1: Discovering all stock topics...")
    t0 = time.time()
    topics = fetch_all_stock_topics()
    print(f"  → {len(topics)} stock topics found ({time.time()-t0:.1f}s)")

    remaining = [t for t in topics if t["id"] not in completed_set]
    total_expected_posts = sum(t["total_posts"] for t in remaining)
    print(f"  → {len(remaining)} topics to scrape ({total_expected_posts} expected posts)")

    # Phase 2: Fetch posts
    print(f"\n⏳ Phase 2: Fetching posts ({MAX_WORKERS} threads)...")
    t1 = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_topic_posts, t["id"], t["title"]): t
            for t in remaining
        }
        done_count = 0
        for future in as_completed(futures):
            topic = futures[future]
            posts = future.result()
            all_posts.extend(posts)
            completed_set.add(topic["id"])
            done_count += 1

            # Checkpoint every 25 topics
            if done_count % 25 == 0:
                ckpt["completed_topics"] = list(completed_set)
                ckpt["all_posts"] = all_posts
                save_checkpoint(ckpt)

            if done_count % 25 == 0 or done_count == len(remaining):
                elapsed = time.time() - t1
                rate = done_count / max(elapsed, 0.1)
                eta = (len(remaining) - done_count) / max(rate, 0.01)
                print(f"  {done_count}/{len(remaining)} topics | "
                      f"{len(all_posts)} posts | "
                      f"{elapsed:.0f}s elapsed | "
                      f"~{eta:.0f}s remaining", flush=True)

    elapsed = time.time() - t1
    print(f"\n  → Done: {len(all_posts)} total posts ({elapsed:.1f}s)")

    # Phase 3: Save to Parquet
    print("\n⏳ Phase 3: Saving to Parquet...")
    df = pd.DataFrame(all_posts)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df = df.sort_values(["topic_id", "created_at"]).reset_index(drop=True)
    df = df.drop_duplicates(subset=["post_id"])  # Safety: no dupes
    df.to_parquet(OUT_PARQUET, index=False)

    total_time = time.time() - t0
    print(f"\n{'='*70}")
    print(f"✅ COMPLETE")
    print(f"   Posts:    {len(df):,}")
    print(f"   Topics:  {df['topic_id'].nunique()}")
    print(f"   Date range: {df['created_at'].min().date()} → {df['created_at'].max().date()}")
    print(f"   Industries: {df['industry'].nunique()}")
    print(f"   File:     {OUT_PARQUET}")
    print(f"   Size:     {OUT_PARQUET.stat().st_size / (1024*1024):.1f} MB")
    print(f"   Time:     {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"{'='*70}")

    # Clean up checkpoint
    clear_checkpoint()


def run_incremental_update():
    print("=" * 70)
    print("VALUEPICKR HISTORICAL SCRAPER — INCREMENTAL UPDATE")
    print("=" * 70)

    if not OUT_PARQUET.exists():
        print("❌ No existing Parquet found. Run --mode full first.")
        return

    existing_df = pd.read_parquet(OUT_PARQUET)
    existing_post_ids = set(existing_df["post_id"].tolist())
    print(f"  Existing: {len(existing_df):,} posts across {existing_df['topic_id'].nunique()} topics")

    # Get all topics
    print("\n⏳ Discovering topics...")
    topics = fetch_all_stock_topics()
    print(f"  → {len(topics)} stock topics")

    # Fetch new posts for each topic
    print(f"\n⏳ Fetching new posts ({MAX_WORKERS} threads)...")
    t0 = time.time()
    new_posts = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_topic_posts, t["id"], t["title"], existing_post_ids): t
            for t in topics
        }
        done_count = 0
        for future in as_completed(futures):
            posts = future.result()
            new_posts.extend(posts)
            done_count += 1
            if done_count % 50 == 0 or done_count == len(topics):
                print(f"  {done_count}/{len(topics)} topics | {len(new_posts)} new posts", flush=True)

    if new_posts:
        new_df = pd.DataFrame(new_posts)
        new_df["created_at"] = pd.to_datetime(new_df["created_at"], utc=True)
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["post_id"])
        combined = combined.sort_values(["topic_id", "created_at"]).reset_index(drop=True)
        combined.to_parquet(OUT_PARQUET, index=False)
        print(f"\n✅ Added {len(new_posts)} new posts. Total: {len(combined):,}")
    else:
        print("\n✅ No new posts found. Data is up to date.")

    print(f"   Time: {time.time()-t0:.0f}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "update"], default="full")
    args = parser.parse_args()

    if args.mode == "full":
        run_full_scrape()
    else:
        run_incremental_update()


if __name__ == "__main__":
    main()
