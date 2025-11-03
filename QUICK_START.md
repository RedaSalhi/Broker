# Quick Start Guide

## Installation (5 minutes)

### Option 1: Using Setup Script (Recommended)
```bash
chmod +x setup.sh
./setup.sh
```

### Option 2: Manual Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
python3 test_platform.py

# Start the application
python3 app.py
```

## Access the Platform

Open your browser and go to:
```
http://localhost:5000
```

## First Steps

### 1. Calculate Option Price

**Dashboard → Option Pricing Calculator**

Example:
- Symbol: `AAPL`
- Strike: `150`
- Days to Expiry: `30`
- Option Type: `call`
- Click "Calculate Price"

You'll see:
- Option price and premium
- Greeks (Delta, Gamma, Vega, Theta, Rho)
- Required hedge shares

### 2. Sell Your First Option

After calculating price:
1. Click "Sell This Option"
2. Enter expiration date
3. Enter quantity: `-10` (negative for short/sell)
4. Confirm premium
5. Click "Execute Sale"

### 3. Execute Delta Hedge

**Positions Page → Find Position → Click "Hedge"**

The system will:
- Calculate required hedge shares
- Execute stock purchase/sale
- Track transaction costs
- Update position delta

### 4. Monitor P&L

**Analytics Page**

View:
- Total P&L
- Win rate and profit factor
- P&L chart over time
- Portfolio Greeks

## Common Operations

### Check Portfolio Greeks
```
Dashboard → Portfolio Greeks section
```

### Auto-Rehedge All Positions
```
Dashboard → "Auto Rehedge Portfolio" button
```

### View Position Details
```
Positions → Click "Details" on any position
```

### Close a Position
```
Positions → Click "Close" on position → Confirm
```

## API Examples

### Get Stock Price
```bash
curl http://localhost:5000/api/market-data/AAPL
```

### Price an Option
```bash
curl -X POST http://localhost:5000/api/price-option \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "strike": 150,
    "days_to_expiry": 30,
    "option_type": "call",
    "num_contracts": 1
  }'
```

### Get Portfolio P&L
```bash
curl http://localhost:5000/api/portfolio-pnl
```

### Get Portfolio Greeks
```bash
curl http://localhost:5000/api/portfolio-greeks
```

## Example Workflow: Selling a Covered Call

### Step 1: Check Stock Price
- Dashboard → Market Data
- Enter: `AAPL`
- Note current price and volatility

### Step 2: Price the Option
- Option Pricing Calculator
- Symbol: `AAPL`
- Strike: Choose strike above current price (e.g., if AAPL = $150, use $155)
- Days to Expiry: `30`
- Option Type: `call`
- Calculate

### Step 3: Sell the Option
- Click "Sell This Option"
- Quantity: `-10` (selling 10 contracts)
- Confirm premium
- Execute

### Step 4: Delta Hedge (Optional)
- Go to Positions
- Find your new position
- Click "Hedge"
- System calculates and executes hedge

### Step 5: Monitor
- Watch position on Positions page
- Check P&L on Analytics page
- Rehedge if delta exceeds threshold

## Keyboard Shortcuts

- Dashboard: Press `1`
- Positions: Press `2`
- Analytics: Press `3`

## Tips

### For Better Pricing
- Use recent market data (refresh if needed)
- Check implied volatility from options chain
- Compare with market prices

### For Better Hedging
- Hedge immediately after selling
- Set rehedge threshold appropriately (default 10%)
- Monitor transaction costs

### For Better Risk Management
- Diversify across underlyings
- Watch concentration limits
- Monitor expiring positions
- Review Greeks regularly

## Troubleshooting

### "No market data" error
- Check internet connection
- API might be rate-limited (wait 60 seconds)
- Try different symbol

### Position not showing
- Refresh the page
- Check Positions page
- Verify it was created (check console logs)

### Can't calculate IV
- Market price might be below intrinsic value
- Check inputs for errors
- Try different volatility estimate

## Configuration

Edit `config.py` to change:
- Risk limits
- Commission rates
- Rehedge threshold
- API keys

## Data Sources

- **Stock Prices:** Yahoo Finance (primary), Alpha Vantage (backup)
- **Options Data:** Yahoo Finance
- **Risk-Free Rate:** 10-year Treasury (^TNX)
- **Volatility:** Historical volatility calculation

## Support

Questions or issues?
- Check README.md for detailed documentation
- Review test_platform.py for examples
- Email: reda.salhi@centrale-med.fr

## Next Steps

1. **Learn the Platform:** Explore all three pages
2. **Paper Trade:** Practice with small quantities
3. **Understand Greeks:** Study how they change
4. **Monitor Risk:** Set up alerts and limits
5. **Analyze Performance:** Review analytics regularly

## Advanced Usage

### Custom Risk Limits
Edit database directly or modify `data/database.py`

### Bulk Operations
Use API endpoints with scripts

### Historical Analysis
Query P&L snapshots from database

### Stress Testing
Use risk_management.py stress_test() function

---

**Ready to trade!** Start with the Dashboard and explore the platform.
