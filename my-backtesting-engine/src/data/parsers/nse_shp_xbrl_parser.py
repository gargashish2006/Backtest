import xml.etree.ElementTree as ET
import re
import io

class NSEShpXbrlParser:
    """Parses NSE Shareholding Pattern XBRL files."""

    def __init__(self, xbrl_content: bytes):
        self.root = ET.fromstring(xbrl_content)
        # Extract namespaces
        self.ns = dict([node for _, node in ET.iterparse(io.BytesIO(xbrl_content), events=['start-ns'])])
        # Manually finding the main namespace if not correctly parsed by iterparse start-ns sometimes
        if not self.ns:
             # Basic fallback
             self.ns = {
                 'in-bse-shp': 'http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-shp',
                 'xbrli': 'http://www.xbrl.org/2003/instance'
             }
        
    def _find_value(self, tag_name):
        # Because namespaces can be tricky, let's try searching by tag name ignoring NS or using known NS
        # Primary method: use the namespace map if available
        # Fallback: iterate and match string
        
        # Try finding with namespace
        for prefix, uri in self.ns.items():
            tag = f"{{{uri}}}{tag_name}"
            matches = self.root.findall(f".//{tag}")
            for m in matches:
                # We need to filter by context usually e.g. 'ShareholdingPattern_ContextI' for total
                context = m.attrib.get('contextRef', '')
                if 'ShareholdingPattern_Context' in context: 
                     return m.text
        
        # Fallback loop
        for elem in self.root.iter():
            if elem.tag.endswith(tag_name):
                 context = elem.attrib.get('contextRef', '')
                 if 'ShareholdingPattern_Context' in context:
                     return elem.text
        return None

    def parse(self):
        """Extracts key metrics."""
        summary = {
            'total_shares': 0,
            'total_shareholders': 0,
            'promoter_pct': 0.0,
            'public_pct': 0.0,
            'fii_pct': 0.0,
            'dii_pct': 0.0
        }
        
        # Iterate all elements
        for elem in self.root.iter():
            tag = elem.tag.split('}')[-1]
            context = elem.attrib.get('contextRef', '')
            if not context or not elem.text:
                continue
                
            val_str = elem.text.strip()
            if not val_str:
                continue

            # Percentages
            if tag == 'ShareholdingAsAPercentageOfTotalNumberOfShares':
                try:
                    val = float(val_str)
                    
                    # Logic to identify context
                    # Current/Total
                    # Note: usually we don't get % for total (it's 100), but sometimes we do.
                    # We primarily care about the breakdown.
                    
                    # Promoter
                    # 'PromoterAndPromoterGroup' is the standard concept
                    # We must exclude 'Trusts...' which also contain this string but have 0 value usually
                    if 'PromoterAndPromoterGroup' in context and 'Trust' not in context:
                        summary['promoter_pct'] = val
                    elif 'Promoter' in context and 'NonPromoter' not in context and 'GovernmentIsPromoter' not in context and 'OtherThanPromoter' not in context and 'Trust' not in context:
                        # Fallback
                        summary['promoter_pct'] = val
                    
                    # Public
                    elif 'Public' in context and 'NonPromoter' not in context:
                        summary['public_pct'] = val
                        
                    # FII/FPI (InstitutionsForeign)
                    elif 'Foreign' in context and 'Institutions' in context:
                        # Sometimes there are mulitple foreign categories (FII, FPI count 1, 2)
                        # We might need to be careful if this overwrites. 
                        # Usually 'InstitutionsForeign' is the aggregate.
                        summary['fii_pct'] = val
                        
                    # DII (InstitutionsDomestic)
                    elif 'Domestic' in context and 'Institutions' in context:
                        summary['dii_pct'] = val
                        
                except ValueError:
                    pass

            # Absolute Numbers
            if tag == 'NumberOfShares':
                 # Total context is usually 'ShareholdingPattern' or 'ShareholdingPattern_Context'
                 if 'ShareholdingPattern' in context and 'Promoter' not in context and 'Public' not in context:
                     try:
                         summary['total_shares'] = int(val_str)
                     except: pass
            
            if tag == 'NumberOfShareholders':
                 if 'ShareholdingPattern' in context and 'Promoter' not in context and 'Public' not in context:
                     try:
                         summary['total_shareholders'] = int(val_str)
                     except: pass
        
        # Normalize percentages if they are in 0-1 format
        # Check sum of promoter + public (should be ~100 or ~1)
        promoter = summary.get('promoter_pct', 0)
        public = summary.get('public_pct', 0)
        
        # If we have both and they sum to approx 1.0, scaling is needed
        # Or if we have just one and it is <= 1.0 and > 0, it is ambiguous but likely 0-1 if high holding.
        # Safer bet: if sum is roughly 1.0.
        
        total_holding = promoter + public
        if 0.9 <= total_holding <= 1.1:
            # likely fractions
            for key in ['promoter_pct', 'public_pct', 'fii_pct', 'dii_pct']:
                if key in summary:
                    summary[key] = summary[key] * 100.0
                    
        return summary

if __name__ == "__main__":
    with open("sample_shp.xml", "rb") as f:
        content = f.read()
    
    parser = NSEShpXbrlParser(content)
    print(parser.parse())
