import requests
from bs4 import BeautifulSoup

def inspect_bse_shp(scrip_code):
    # Try the standard SHP page
    url = f"https://www.bseindia.com/corporates/ShareholdingPattern.aspx?scripcd={scrip_code}&flag=New"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    print(f"Fetching {url}")
    try:
        resp = requests.get(url, headers=headers)
        print(f"Status: {resp.status_code}")
        # print(resp.text[:500])
        
        # Check for XBRL links
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # Look for links that might be XBRL
        links = soup.find_all('a')
        for link in links:
            href = link.get('href', '')
            text = link.text.strip()
            if 'xml' in href.lower() or 'xbrl' in href.lower() or 'zip' in href.lower():
                print(f"Found potential XBRL/Zip: {text} -> {href}")
                
            # print(f"Link: {text} -> {href}") # Debugging
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_bse_shp("533022") # 20 Microns
