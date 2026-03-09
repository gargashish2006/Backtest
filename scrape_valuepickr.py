"""
Scrape ValuePickr forum via Discourse JSON API (v3 - using /latest.json).
Uses the /latest.json endpoint which correctly includes ALL subcategory topics.
"""
import requests
import time
import json
from datetime import datetime, timedelta, timezone

BASE_URL = "https://forum.valuepickr.com"
CUTOFF = datetime.now(timezone.utc) - timedelta(days=30)

# ALL stock-related category IDs (includes subcategories)
STOCK_CATEGORY_IDS = {11, 14, 18, 19, 21, 69}
# 11 = Stock Opportunities, 14 = Fundamental Analysis
# 18 = Recommended, 19 = Recommended Buy
# 21 = Portfolios/Ideas, 69 = New Arrivals

def fetch_all_topics():
    """Fetch all topics with recent activity using /latest.json, filter by stock categories."""
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
            
            # Skip non-stock categories
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
                
            topics.append({
                "id": tid,
                "title": t.get("fancy_title", t.get("title", ""))
                          .replace("&rsquo;", "'").replace("&amp;", "&").replace("&ndash;", "-"),
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
    """Count posts in the last 30 days by fetching from the END of the topic."""
    url = f"{BASE_URL}/t/{topic_id}.json"
    try:
        resp = requests.get(url, headers={"Accept": "application/json"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return 0
    
    post_stream = data.get("post_stream", {})
    all_post_ids = post_stream.get("stream", [])
    
    if not all_post_ids:
        return 0
    
    # For small topics, all posts are in initial response
    if total_posts <= 20:
        posts = post_stream.get("posts", [])
        return sum(1 for p in posts 
                   if p.get("created_at") and 
                   datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")) >= CUTOFF)
    
    # For large topics, fetch from the END working backwards
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
        
        time.sleep(0.2)
    
    return recent_count


def main():
    print("="*70)
    print("VALUEPICKR FORUM - 30 DAY MESSAGE COUNT ANALYSIS (v3)")
    print(f"Cutoff: {CUTOFF.strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*70)
    
    print("\n--- Phase 1: Fetching all active stock topics ---")
    topics = fetch_all_topics()
    print(f"\nFound {len(topics)} stock topics with activity in last 30 days.")
    
    print("\n--- Phase 2: Counting recent posts per topic ---")
    for i, t in enumerate(topics):
        short_title = t['title'][:50]
        print(f"  [{i+1}/{len(topics)}] {short_title}...", end=" ", flush=True)
        recent = count_recent_posts(t["id"], t["total_posts"])
        t["recent_posts_30d"] = recent
        print(f"-> {recent} posts")
        time.sleep(0.2)
    
    # Sort by 30d post count
    topics.sort(key=lambda x: x.get("recent_posts_30d", 0), reverse=True)
    
    # Display results
    active = [t for t in topics if t.get("recent_posts_30d", 0) > 0]
    
    print("\n" + "="*90)
    print(f"{'Rank':<5} {'Company/Topic':<55} {'30d Posts':<10} {'Total':<8} {'Views':<10}")
    print("="*90)
    for i, r in enumerate(active, 1):
        title = r["title"][:53]
        print(f"{i:<5} {title:<55} {r['recent_posts_30d']:<10} {r['total_posts']:<8} {r['views']:<10}")
    print("="*90)
    print(f"Total stock topics analyzed: {len(topics)}")
    print(f"Topics with >= 1 post in 30d: {len(active)}")
    
    # Save
    out_path = "/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/valuepickr_30d_counts.json"
    with open(out_path, "w") as f:
        json.dump(topics, f, indent=2, default=str)
    print(f"\nFull results saved to: {out_path}")


if __name__ == "__main__":
    main()
