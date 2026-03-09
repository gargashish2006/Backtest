"""
Scrape ValuePickr forum: 3-month (90-day) message counts aggregated by industry.
Maps stock names to industries using industry_info.csv from the database.
"""
import requests
import time
import json
import csv
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

BASE_URL = "https://forum.valuepickr.com"
CUTOFF = datetime.now(timezone.utc) - timedelta(days=90)
REPO = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")

STOCK_CATEGORY_IDS = {11, 14, 18, 19, 21, 69}

# Manual industry mapping for companies that may not match our database exactly
MANUAL_INDUSTRY = {
    "IDFC First Bank": "Banks",
    "Bandhan Bank": "Banks",
    "Tamilnad Mercantile Bank": "Banks",
    "Equitas Small Finance Bank": "Banks",
    "CSB BANK": "Banks",
    "South Indian Bank": "Banks",
    "HDFC Bank": "Banks",
    "Ujjivan Small Finance Bank": "Banks",
    "E2E Networks": "IT - Software",
    "Zaggle": "IT - Software",
    "All E Technologies": "IT - Software",
    "Dynacons Systems": "IT - Software",
    "NPST": "IT - Software",
    "KPIT": "IT - Software",
    "Intellect Design Arena": "IT - Software",
    "Affle India": "IT - Software",
    "NetWeb Technologies": "IT - Software",
    "Ceinsys Tech": "IT - Software",
    "Genesys International": "IT - Software",
    "MPS Ltd": "IT - Software",
    "Ola Electric": "Electric Vehicles",
    "Waaree Energies": "Solar Energy",
    "Vikram Solar": "Solar Energy",
    "HBL Engineering": "Electronics",
    "Avanti Feeds": "Aquaculture",
    "MTAR Technologies": "Industrial Manufacturing",
    "Kalyani Cast-Tech": "Iron & Steel Products",
    "Kiri Industries": "Dyes And Pigments",
    "BSE": "Exchange and Data Platform",
    "MCX": "Exchange and Data Platform",
    "Indian Energy Exchange": "Exchange and Data Platform",
    "CDSL": "Depositories, Clearing Houses and Other Intermediaries",
    "Manorama Industries": "Edible Oil",  
    "Kovai Medical": "Hospitals & Diagnostic Centres",
    "3B Blackbio DX": "Hospitals & Diagnostic Centres",
    "Muthoot Finance": "Non Banking Financial Company (NBFC)",
    "Muthoot Microfin": "Non Banking Financial Company (NBFC)",
    "Manappuram Finance": "Non Banking Financial Company (NBFC)",
    "Ugro Capital": "Non Banking Financial Company (NBFC)",
    "Aavas Financiers": "Non Banking Financial Company (NBFC)",
    "Edelweiss Financial": "Non Banking Financial Company (NBFC)",
    "Arman Financial": "Non Banking Financial Company (NBFC)",
    "Five Star Business Finance": "Non Banking Financial Company (NBFC)",
    "CreditAccess Grameen": "Non Banking Financial Company (NBFC)",
    "Praj Industries": "Industrial Manufacturing",
    "Afcom Holdings": "Logistics",
    "Interarch": "Construction",
    "BLS International": "Outsourcing & Consulting",
    "CONNPLEX CINEMA": "Entertainment",
    "Concord Control Systems": "Railways",
    "Time Technoplast": "Plastic Products",
    "Kernex": "Railways",
    "CarTrade Tech": "Internet & Catalogue Retail",
    "Anant Raj": "Real Estate",
    "Deep Industries": "Oil & Gas",
    "Natco Pharma": "Pharmaceuticals",
    "Supriya Lifescience": "Pharmaceuticals",
    "Kwality Pharmaceuticals": "Pharmaceuticals",
    "Windlas Biotech": "Pharmaceuticals",
    "Zydus Lifesciences": "Pharmaceuticals",
    "Aarti Pharma Labs": "Pharmaceuticals",
    "Gravita India": "Non-Ferrous Metals",
    "Bharti Airtel": "Telecom",
    "TD Power Systems": "Heavy Electrical Equipment",
    "Lumax Auto": "Auto Components & Equipments",
    "Hawkins Cookers": "Consumer Durables",
    "La Opala": "Consumer Durables",
    "Kaynes Technology": "Electronics",
    "Religare Enterprises": "Finance",
    "IGI India": "Diamond, Gems and Jewellery",
    "Info Edge": "IT - Software",
    "Sterlite Technologies": "Telecom Cables",
    "Deccan Gold": "Mining & Mineral products",
    "Zomato": "Internet & Catalogue Retail",
    "Brainbees": "Internet & Catalogue Retail",
    "FirstCry": "Internet & Catalogue Retail",
    "Mobikwik": "IT - Software",
    "Piramal Finance": "Non Banking Financial Company (NBFC)",
    "SEPC LTD": "Construction",
    "Sandhar Technologies": "Auto Components & Equipments",
    "Shivalik Bimetal": "Electronics",
    "Tata Power": "Power Generation & Distribution",
    "Hindustan Aeronautics": "Defence",
    "Force Motors": "Automobiles",
    "Bajaj Auto": "Automobiles",
    "Titan Company": "Diamond, Gems and Jewellery",
    "Nykaa": "Internet & Catalogue Retail",
    "Avenue Supermart": "Retailing",
    "PVR": "Entertainment",
    "Lemon Tree Hotels": "Hotels / Hospitality",
    "Sai Life Sciences": "Pharmaceuticals",
    "Vintage Coffee": "Plantation & Plantation Products",
    "Nuclear Energy": "Power Generation & Distribution",
    "ASM Technologies": "IT - Software",
    "Cybele Ind": "Cables",
    "ICICI Prudential": "Asset Management",
    "Dishman Carbogen": "Pharmaceuticals",
    "Cohance life science": "Pharmaceuticals",
    "Yatharth Hospital": "Hospitals & Diagnostic Centres",
    "Shalby Hospitals": "Hospitals & Diagnostic Centres",
    "Rainbow Children": "Hospitals & Diagnostic Centres",
    "Dr Lal PathLabs": "Hospitals & Diagnostic Centres",
    "Thyrocare": "Hospitals & Diagnostic Centres",
    "Krsnaa Diagnostics": "Hospitals & Diagnostic Centres",
    "Max Healthcare": "Hospitals & Diagnostic Centres",
    "Sagility India": "IT - Software",
    "Steelcast": "Iron & Steel Products",
    "20 Microns": "Mining & Mineral products",
    "EMS Limited": "Construction",
    "Borana Weaves": "Textiles",
    "Rossari Biotech": "Specialty Chemicals",
    "Vinati Organics": "Specialty Chemicals",
    "Himadri Specialty": "Specialty Chemicals",
    "Kesar Petroproducts": "Specialty Chemicals",
    "Sharda Cropchem": "Agrochemicals",
    "Kaveri seeds": "Agrochemicals",
    "Radico khaitan": "Alcoholic Beverages",
    "Marico": "FMCG",
    "Hatsun Agro": "FMCG",
    "KRBL": "FMCG",
    "Piccadily Agro": "Alcoholic Beverages",
    "UPL": "Agrochemicals",
    "Vedanta": "Non-Ferrous Metals",
    "Hindustan Zinc": "Non-Ferrous Metals",
    "3M India": "Diversified",
    "L&T": "Construction",
    "Cipla": "Pharmaceuticals",
    "JSW Infrastructure": "Infrastructure",
    "Gujarat Intrux": "Iron & Steel Products",
    "Gandhar Oil": "Petrochemicals",
    "Tinna rubber": "Plastic Products",
    "Ashiana Housing": "Real Estate",
    "Arkade Developers": "Real Estate",
    "Krishna Defence": "Defence",
    "C2C Advanced Systems": "Defence",
    "Zen technologies": "Defence",
    "JNK India": "Oil & Gas",
    "CFF Fluid Control": "Industrial Manufacturing",
    "GG Automotive": "Auto Components & Equipments",
    "S Chand": "Media & Publishing",
    "MIDHANI": "Non-Ferrous Metals",
    "Beta Drugs": "Pharmaceuticals",
    "Innova Captab": "Pharmaceuticals",
    "Neuland Laboratories": "Pharmaceuticals",
    "Shilpa Medicare": "Pharmaceuticals",
    "Kopran": "Pharmaceuticals",
    "Influx HealthTech": "Pharmaceuticals",
    "EFC": "IT - Software",
    "Macfos": "Internet & Catalogue Retail",
    "Goldiam International": "Diamond, Gems and Jewellery",
    "SJS Enterprises": "Auto Components & Equipments",
    "Carysil": "Consumer Durables",
    "AGI Greenpac": "Packaging",
    "Shree Refrigerations": "Consumer Durables",
    "H.G. Infra": "Construction",
    "Multibase India": "Plastic Products",
    "Dhabriya Polywood": "Plastic Products",
    "DDev Plastiks": "Plastic Products",
    "BCL Industries": "Edible Oil",
    "South West Pinnacle": "Construction",
    "Kings Infra": "Aquaculture",
    "Avalon Technologies": "Electronics",
    "Krishca Ltd": "Iron & Steel Products",
    "Sambhv Steel": "Iron & Steel Products",
    "Maharashtra seamless": "Iron & Steel Products",
    "Surya roshni": "Iron & Steel Products",
    "Mayur Uniquoters": "Textiles",
    "Ambika Cotton": "Textiles",
    "Insecticides India": "Agrochemicals",
    "Pricol": "Auto Components & Equipments",
    "Permanent Magnets": "Industrial Manufacturing",
    "Sakar Healthcare": "Pharmaceuticals",
    "Inox India": "Industrial Manufacturing",
    "Shilchar Technologies": "Heavy Electrical Equipment",
    "Elecon Engineering": "Industrial Manufacturing",
    "Skipper": "Power Generation & Distribution",
    "Styrenix": "Specialty Chemicals",
    "Marico Kaya": "Personal Care",
    "Timex Group": "Consumer Durables",
    "Kamat Hotels": "Hotels / Hospitality",
    "GPT Infra": "Railways",
    "Accent Microcell": "Plastic Products",
    "TBO Tek": "Internet & Catalogue Retail",
    "Kontor Space": "Real Estate",
    "RBM Infra": "Construction",
    "ADAG Group": "Diversified",
    "Security and Intelligence": "Outsourcing & Consulting",
    "Sammaan Capital": "Non Banking Financial Company (NBFC)",
    "Balu Forge": "Industrial Manufacturing",
    "Knowledge Marine": "Logistics",
    "Aeroflex Industries": "Industrial Manufacturing",
    "Semiconductor": "Electronics",
    "Rare Earth": "Mining & Mineral products",
    "Geospatial sector": "IT - Software",
    "HDFC Life": "Life Insurance",
    "Rossell Techsys": "Defence",
    "Senores Pharma": "Pharmaceuticals",
    "EPACK PREFAB": "Construction",
    "Arihant Foundations": "Real Estate",
    "Nurture Well": "FMCG",
    "Crizac": "Construction",
    "Canara Robeco AMC": "Asset Management",
    "Empire Industries": "Consumer Durables",
    "Safe Enterprises": "Retailing",
}


def fetch_all_topics():
    topics = []
    seen_ids = set()
    page = 0
    
    while True:
        url = f"{BASE_URL}/latest.json?page={page}&no_definitions=true"
        print(f"Fetching /latest.json page {page}...")
        try:
            resp = requests.get(url, headers={"Accept": "application/json"}, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"  Error: {e}")
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
            
            if last_dt < CUTOFF:
                stopped_early = True
                break
            
            if t.get("pinned", False):
                continue
                
            title = (t.get("fancy_title", t.get("title", ""))
                      .replace("&rsquo;", "'").replace("&amp;", "&").replace("&ndash;", "-"))
            
            topics.append({
                "id": tid,
                "title": title,
                "total_posts": t.get("posts_count", 0),
                "last_posted_at": last_posted,
                "views": t.get("views", 0),
                "like_count": t.get("like_count", 0),
                "category_id": cat_id,
            })
        
        if stopped_early or "more_topics_url" not in topic_list:
            break
        
        page += 1
        time.sleep(0.3)
    
    return topics


def count_recent_posts(topic_id, total_posts):
    url = f"{BASE_URL}/t/{topic_id}.json"
    try:
        resp = requests.get(url, headers={"Accept": "application/json"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except:
        return 0
    
    post_stream = data.get("post_stream", {})
    all_post_ids = post_stream.get("stream", [])
    
    if not all_post_ids:
        return 0
    
    if total_posts <= 20:
        posts = post_stream.get("posts", [])
        return sum(1 for p in posts 
                   if p.get("created_at") and 
                   datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")) >= CUTOFF)
    
    recent_count = 0
    chunk_size = 20
    
    for start_idx in range(len(all_post_ids) - 1, -1, -chunk_size):
        end_idx = max(start_idx - chunk_size + 1, 0)
        chunk_ids = all_post_ids[end_idx:start_idx + 1]
        if not chunk_ids:
            break
        
        params = "&".join([f"post_ids[]={pid}" for pid in chunk_ids])
        chunk_url = f"{BASE_URL}/t/{topic_id}/posts.json?{params}"
        
        try:
            resp = requests.get(chunk_url, headers={"Accept": "application/json"}, timeout=15)
            resp.raise_for_status()
            chunk_data = resp.json()
        except:
            break
        
        chunk_posts = chunk_data.get("post_stream", {}).get("posts", [])
        found_old = False
        for p in chunk_posts:
            created = p.get("created_at", "")
            if created:
                pdt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if pdt >= CUTOFF:
                    recent_count += 1
                else:
                    found_old = True
        
        if found_old:
            break
        time.sleep(0.15)
    
    return recent_count


def map_to_industry(title):
    """Map a topic title to an industry using manual mapping."""
    for key, industry in MANUAL_INDUSTRY.items():
        if key.lower() in title.lower():
            return industry
    return "Other / Unclassified"


def main():
    print("="*70)
    print("VALUEPICKR - 3 MONTH INDUSTRY SENTIMENT ANALYSIS")
    print(f"Cutoff: {CUTOFF.strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*70)
    
    print("\n--- Phase 1: Fetching all active stock topics (90 days) ---")
    topics = fetch_all_topics()
    print(f"\nFound {len(topics)} stock topics with activity in last 90 days.")
    
    print("\n--- Phase 2: Counting recent posts per topic ---")
    for i, t in enumerate(topics):
        short_title = t['title'][:50]
        print(f"  [{i+1}/{len(topics)}] {short_title}...", end=" ", flush=True)
        recent = count_recent_posts(t["id"], t["total_posts"])
        t["recent_posts_90d"] = recent
        t["industry"] = map_to_industry(t["title"])
        print(f"-> {recent} posts [{t['industry']}]")
        time.sleep(0.15)
    
    # Aggregate by industry
    industry_counts = defaultdict(lambda: {"posts": 0, "topics": 0, "companies": []})
    for t in topics:
        ind = t["industry"]
        posts = t.get("recent_posts_90d", 0)
        if posts > 0:
            industry_counts[ind]["posts"] += posts
            industry_counts[ind]["topics"] += 1
            industry_counts[ind]["companies"].append((t["title"][:40], posts))
    
    # Sort by total posts
    sorted_industries = sorted(industry_counts.items(), key=lambda x: x[1]["posts"], reverse=True)
    
    print("\n" + "="*90)
    print(f"{'Rank':<5} {'Industry':<45} {'3M Posts':<10} {'Topics':<8} {'Top Company':<30}")
    print("="*90)
    for i, (ind, data) in enumerate(sorted_industries, 1):
        top_company = max(data["companies"], key=lambda x: x[1])[0] if data["companies"] else ""
        print(f"{i:<5} {ind[:43]:<45} {data['posts']:<10} {data['topics']:<8} {top_company:<30}")
    print("="*90)
    
    # Save
    out = {
        "cutoff": CUTOFF.isoformat(),
        "total_topics": len(topics),
        "industry_summary": {ind: {"total_posts_90d": d["posts"], "topic_count": d["topics"], 
                                     "companies": d["companies"]} 
                             for ind, d in sorted_industries},
        "topics": topics
    }
    out_path = REPO / "valuepickr_3m_industry_counts.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    main()
