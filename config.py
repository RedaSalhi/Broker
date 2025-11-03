"""
Configuration file for Options Trading Platform
"""
import os

# API Configuration
ALPHA_VANTAGE_API_KEY = ''

# Email Configuration
EMAIL_RECIPIENT = ''
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

# Database Configuration
DATABASE_URI = 'sqlite:///options_platform.db'

# Trading Configuration
OPTIONS_MULTIPLIER = 100  # Standard options contract multiplier
RISK_FREE_RATE = 0.05  # Default risk-free rate (5%)
REHEDGE_THRESHOLD = 0.10  # Rehedge when delta changes by 10%

# Risk Limits
MAX_POSITION_SIZE = 100  # Maximum contracts per position
MAX_DELTA_EXPOSURE = 10000  # Maximum portfolio delta exposure
MAX_VEGA_EXPOSURE = 5000  # Maximum portfolio vega exposure
MAX_CONCENTRATION = 0.30  # Maximum 30% in single underlying

# Commission and Costs
STOCK_COMMISSION = 0.01  # $0.01 per share
OPTIONS_COMMISSION = 0.65  # $0.65 per contract
BID_ASK_SPREAD = 0.01  # 1% average bid-ask spread

# Cache Configuration
MARKET_DATA_CACHE_SECONDS = 60  # Cache market data for 60 seconds
API_RATE_LIMIT_PER_MINUTE = 5  # Alpha Vantage free tier limit

# Flask Configuration
SECRET_KEY = os.urandom(24)
DEBUG = True
HOST = '0.0.0.0'
PORT = 5001
