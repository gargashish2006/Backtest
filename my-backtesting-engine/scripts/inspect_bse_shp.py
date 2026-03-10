import requests
from bs4 import BeautifulSoup
import sys

def inspect_bse_shp(scrip_code):
    # Try the SHP landing page which might contain links to quarters
    # Url pattern found: https://www.bseindia.com/stock-share-price/bharti-airtel-ltd/bhartiartl/{scrip_code}/shareholding-pattern/
    # But usually the URL requires the company name and short code. 
    # However, BSE often resolves partial URLs or we can find a generic one.
    
    # Generic format often used: https://www.bseindia.com/stock-share-price/-/-/{scrip_code}/shareholding-pattern/
    # Let's see if that works.
    
    url = f"https://www.bseindia.com/stock-share-price/-/-/{scrip_code}/shareholding-pattern/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    print(f"Fetching {url}...")
    try:
        response = requests.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a')
            print("\n--- Links in SHP Landing Page ---")
            found_qtr = False
            for a in links:
                href = a.get('href', '')
                if 'qtrid' in href:
                    print(f"Quarter Link: {a.get_text().strip()} -> {href}")
                    found_qtr = True
                if 'XBRL' in a.get_text() or 'xbrl' in href.lower():
                     print(f"XBRL Link: {a.get_text().strip()} -> {href}")
            
            if not found_qtr:
                print("No 'qtrid' links found. Dumping all hrefs containing 'shareholding'...")
                for a in links:
                    href = a.get('href', '')
                    if 'shareholding' in href.lower():
                         print(f"Possible Link: {a.get_text().strip()} -> {href}")

    except Exception as e:
        print(f"Error: {e}")
        
    return

if __name__ == "__main__":
    inspect_bse_shp("532454") # Bharti Airtel
