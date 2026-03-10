#!/bin/bash
# Update price data to latest date (Feb 9, 2026)
# This script will:
# 1. Download new data from Feb 6-9, 2026
# 2. Verify corporate actions at overlap date
# 3. Merge with existing database
# 4. Flag any potential adjustments needed

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Price Data Update to Feb 9, 2026${NC}"
echo -e "${GREEN}=====================================${NC}"

# Check if environment variables are set
if [ -z "$DHAN_CLIENT_ID" ] || [ -z "$DHAN_ACCESS_TOKEN" ]; then
    echo -e "${RED}ERROR: Dhan API credentials not set!${NC}"
    echo ""
    echo "Please set the following environment variables:"
    echo "  export DHAN_CLIENT_ID=\"your_client_id\""
    echo "  export DHAN_ACCESS_TOKEN=\"your_access_token\""
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ Dhan credentials found${NC}"
echo ""

# Check current data status
echo -e "${YELLOW}Current database status:${NC}"
python3 -c "
import pandas as pd
df = pd.read_parquet('database/price_data.parquet')
df['date'] = pd.to_datetime(df['date'])
print(f'  Date range: {df[\"date\"].min().date()} to {df[\"date\"].max().date()}')
print(f'  Total rows: {len(df):,}')
print(f'  Unique stocks: {df[\"isin\"].nunique():,}')
"
echo ""

# Run the update script
echo -e "${GREEN}Starting update from 2026-02-06 to 2026-02-09...${NC}"
echo ""

python3 scripts/update_price_data.py 2026-02-06 2026-02-09 --workers 10

echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Update Complete!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# Check if any adjustments are flagged in the output
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Review the output above for any corporate action warnings"
echo "2. If adjustments are needed, run: python3 scripts/apply_adjustments.py"
echo "3. Verify updated data with: python3 -c \"import pandas as pd; df = pd.read_parquet('database/price_data.parquet'); print(df[df['date'] >= '2026-02-06'].groupby('date').size())\""
echo ""
