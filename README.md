# Options Trading Platform with Delta Hedging & P&L Tracking

A professional-grade options trading platform built with Flask for market makers and option sellers. Features real-time pricing using the Black-Scholes model, automated delta hedging, comprehensive P&L tracking, and risk management.

## Features

### Core Functionality
- **Black-Scholes Option Pricing**: Real-time option pricing for calls and puts
- **Greeks Calculator**: Delta, Gamma, Vega, Theta, and Rho calculations
- **Delta Hedging**: Automated delta-neutral hedging with rebalancing
- **P&L Tracking**: Real-time profit/loss tracking for both buyers and sellers
- **Portfolio Management**: Track multiple positions across different underlyings
- **Risk Management**: Position limits, concentration limits, and exposure monitoring
- **Market Data Integration**: Real-time stock prices via Alpha Vantage and Yahoo Finance

### Web Interface
- **Trading Dashboard**: Option pricing calculator and portfolio overview
- **Positions Manager**: View and manage all open/closed positions
- **Analytics Dashboard**: Performance metrics, P&L charts, and risk analysis

## Project Structure

```
options_platform/
├── app.py                 # Main Flask application
├── config.py             # Configuration and API keys
├── requirements.txt      # Python dependencies
├── models/
│   ├── __init__.py
│   ├── black_scholes.py # Black-Scholes pricing model
│   ├── greeks.py        # Greeks calculations
│   └── portfolio.py     # Portfolio management
├── data/
│   ├── __init__.py
│   ├── market_data.py   # Alpha Vantage & Yahoo Finance integration
│   └── database.py      # SQLAlchemy models
├── utils/
│   ├── __init__.py
│   ├── hedging.py       # Delta hedging logic
│   ├── pnl.py          # P&L calculations
│   └── risk_management.py # Risk monitoring and alerts
├── templates/
│   ├── base.html
│   ├── dashboard.html   # Main trading dashboard
│   ├── positions.html   # Current positions view
│   └── analytics.html   # P&L and risk analytics
└── static/
    └── css/
        └── style.css
```

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup Instructions

1. **Clone or navigate to the project directory**
   ```bash
   cd PATH
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure API keys** (already set in config.py)
   - Alpha Vantage API Key: ``

5. **Initialize the database**
   ```bash
   python3 -c "from app import app, init_db; init_db(app)"
   ```

6. **Run the application**
   ```bash
   python3 app.py
   ```

7. **Access the platform**
   - Open your browser and navigate to: `http://localhost:5000`

## Usage Guide

### 1. Option Pricing Calculator

Navigate to the Dashboard and use the Option Pricing Calculator:

1. Enter the stock symbol (e.g., AAPL, TSLA)
2. Set strike price, days to expiry, and option type (call/put)
3. Optional: Enter implied volatility (or let it auto-calculate from historical data)
4. Click "Calculate Price"

**Results include:**
- Option price and total premium
- Greeks (Delta, Gamma, Vega, Theta, Rho)
- Required hedge shares and hedge value

### 2. Selling Options

After calculating an option price:

1. Click "Sell This Option"
2. Enter expiration date
3. Enter quantity (negative for short positions, e.g., -10)
4. Confirm premium
5. Click "Execute Sale"

The position will be created and added to your portfolio.

### 3. Delta Hedging

**Manual Hedge:**
1. Go to Positions page
2. Find the position you want to hedge
3. Click "Hedge" button
4. Confirm the hedge execution

**Automatic Rehedging:**
1. Go to Dashboard
2. Click "Auto Rehedge Portfolio"
3. The system will rehedge all positions exceeding the delta threshold (10%)

### 4. Monitoring P&L

**Individual Position:**
1. Go to Positions page
2. Click "Details" on any position
3. View comprehensive P&L breakdown including:
   - Option P&L
   - Hedge P&L
   - Total P&L and ROI
   - Current Greeks

**Portfolio Level:**
1. Go to Analytics page
2. View performance metrics:
   - Win rate
   - Profit factor
   - Sharpe ratio
   - P&L history chart

### 5. Risk Management

The platform automatically monitors:
- **Delta Exposure**: Maximum portfolio delta
- **Vega Exposure**: Volatility risk
- **Position Size**: Maximum contracts per position
- **Concentration**: Maximum exposure to single underlying

Risk limits are configured in the database and can be customized.

## API Endpoints

### Market Data
- `GET /api/market-data/<symbol>` - Get real-time stock price and volatility
- `GET /api/options-chain/<symbol>` - Get options chain data

### Option Pricing
- `POST /api/price-option` - Calculate option price and Greeks
- `POST /api/calculate-iv` - Calculate implied volatility from market price

### Trading
- `POST /api/sell-option` - Create new option position
- `POST /api/close-position` - Close existing position

### Portfolio & Greeks
- `GET /api/positions` - Get all positions
- `GET /api/position/<id>` - Get specific position details
- `GET /api/portfolio-greeks` - Get portfolio-level Greeks
- `GET /api/portfolio-pnl` - Get portfolio P&L

### Hedging
- `POST /api/calculate-hedge` - Calculate hedge requirements
- `POST /api/execute-hedge` - Execute delta hedge
- `GET /api/delta-exposure` - Get portfolio delta exposure
- `POST /api/auto-rehedge` - Automatically rehedge portfolio

### Analytics
- `GET /api/performance-metrics` - Get performance statistics
- `GET /api/pnl-history` - Get historical P&L data

## Configuration

Edit `config.py` to customize:

### API Configuration
```python
ALPHA_VANTAGE_API_KEY = 'your_key_here'
```

### Trading Configuration
```python
OPTIONS_MULTIPLIER = 100  # Standard options contract multiplier
RISK_FREE_RATE = 0.05     # Default risk-free rate
REHEDGE_THRESHOLD = 0.10  # Rehedge when delta changes by 10%
```

### Risk Limits
```python
MAX_POSITION_SIZE = 100        # Maximum contracts per position
MAX_DELTA_EXPOSURE = 10000     # Maximum portfolio delta
MAX_VEGA_EXPOSURE = 5000       # Maximum portfolio vega
MAX_CONCENTRATION = 0.30       # Maximum 30% in single underlying
```

### Commission and Costs
```python
STOCK_COMMISSION = 0.01        # $0.01 per share
OPTIONS_COMMISSION = 0.65      # $0.65 per contract
BID_ASK_SPREAD = 0.01         # 1% average spread
```

## Technical Details

### Black-Scholes Implementation

The platform uses the standard Black-Scholes formula for European options:

**Call Price:**
```
C = S * N(d1) - K * e^(-rT) * N(d2)
```

**Put Price:**
```
P = K * e^(-rT) * N(-d2) - S * N(-d1)
```

Where:
- `d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)`
- `d2 = d1 - σ√T`
- `N(x)` = cumulative standard normal distribution

### Delta Hedging Strategy

**Hedge Ratio:** `-Δ × Contracts × Multiplier`

For a short call position with Delta = 0.6 and 10 contracts:
- Position Delta = 0.6 × (-10) × 100 = -600
- Hedge Required = +600 shares

**Rehedging Trigger:** When `|Current Delta / Initial Delta - 1| > Threshold`

### P&L Calculation

**For Option Sellers:**
```
P&L = Premium Collected - Current Option Value + Hedge P&L - Transaction Costs
```

**For Option Buyers:**
```
P&L = Current Option Value - Premium Paid
```

## Database Schema

### Positions Table
- Stores all option positions (open, closed, expired)
- Tracks entry details, premiums, and implied volatility

### Hedges Table
- Records all delta hedge transactions
- Links to parent position
- Tracks transaction costs

### P&L Snapshots Table
- Time-series P&L data
- Greeks at each snapshot
- Enables historical analysis

### Market Data Cache
- Caches real-time market data
- Reduces API calls

## Market Data Sources

### Primary: Yahoo Finance (yfinance)
- **Advantages:** Free, unlimited, real-time data
- **Data:** Stock prices, options chains, historical volatility

### Fallback: Alpha Vantage
- **API Key:** MZYTV93Z0A0ZMWF0
- **Rate Limit:** 5 requests per minute (free tier)
- **Data:** Stock quotes, intraday data

## Performance Metrics

The platform calculates:
- **Win Rate:** % of profitable trades
- **Profit Factor:** Total profit / Total loss
- **Sharpe Ratio:** Risk-adjusted returns
- **ROI:** Return on invested capital
- **Average Win/Loss:** Mean profit/loss per trade

## Troubleshooting

### API Rate Limits
If you hit Alpha Vantage rate limits:
- The platform automatically falls back to Yahoo Finance
- Consider upgrading to Alpha Vantage premium
- Increase cache TTL in config

### Database Errors
Reset the database:
```bash
rm options_platform.db
python3 -c "from app import app, init_db; init_db(app)"
```

### Missing Dependencies
```bash
pip install --upgrade -r requirements.txt
```

## Future Enhancements

Potential improvements:
1. **American Options Pricing:** Implement binomial tree model
2. **Volatility Surface:** Build IV surface from options chain
3. **Backtesting Engine:** Test strategies on historical data
4. **Real-time WebSocket:** Live price updates
5. **Advanced Analytics:** VaR, Greeks P&L attribution
6. **Authentication:** User login and multi-user support
7. **Options Strategies:** Spreads, straddles, condors
8. **Machine Learning:** IV prediction, optimal hedge timing

## Security Notes

**For Production Deployment:**
1. Change `SECRET_KEY` in config.py
2. Use environment variables for API keys
3. Enable HTTPS
4. Add authentication/authorization
5. Configure proper SMTP for email alerts
6. Use PostgreSQL instead of SQLite
7. Implement rate limiting
8. Add input validation and sanitization

## Support & Contact

- **Email:** reda.salhi@centrale-med.fr
- **Issues:** Create an issue in the project repository

## License

This project is for educational and authorized trading purposes only. Use at your own risk.

---

**Disclaimer:** This platform is for educational purposes. Options trading involves significant risk. Always conduct proper research and risk management before trading.
