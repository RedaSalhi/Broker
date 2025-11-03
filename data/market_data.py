"""
Market Data Integration

Fetches real-time and historical market data from Alpha Vantage API
and other data sources. Includes caching to manage API rate limits.
"""
import requests
import time
import yfinance as yf
from datetime import datetime, timedelta
from functools import lru_cache
import json


class MarketDataCache:
    """Simple in-memory cache for market data"""

    def __init__(self, ttl_seconds=60):
        self.cache = {}
        self.ttl = ttl_seconds

    def get(self, key):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None

    def set(self, key, value):
        self.cache[key] = (value, time.time())

    def clear(self):
        self.cache.clear()


class AlphaVantageClient:
    """Client for Alpha Vantage API"""

    def __init__(self, api_key, cache_ttl=60):
        self.api_key = api_key
        self.base_url = 'https://www.alphavantage.co/query'
        self.cache = MarketDataCache(ttl_seconds=cache_ttl)
        self.last_request_time = 0
        self.min_request_interval = 12  # 5 requests per minute = 12 seconds between requests

    def _rate_limit(self):
        """Enforce rate limiting"""
        time_since_last_request = time.time() - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _make_request(self, params):
        """Make API request with rate limiting"""
        self._rate_limit()
        response = requests.get(self.base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_stock_price(self, symbol):
        """
        Get current stock price.

        Parameters:
        -----------
        symbol : str
            Stock ticker symbol

        Returns:
        --------
        dict
            Stock price data including price, volume, etc.
        """
        cache_key = f"quote_{symbol}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': self.api_key
        }

        try:
            data = self._make_request(params)

            if 'Global Quote' in data and data['Global Quote']:
                quote = data['Global Quote']
                result = {
                    'symbol': symbol,
                    'price': float(quote.get('05. price', 0)),
                    'change': float(quote.get('09. change', 0)),
                    'change_percent': quote.get('10. change percent', '0%'),
                    'volume': int(quote.get('06. volume', 0)),
                    'timestamp': datetime.now()
                }
                self.cache.set(cache_key, result)
                return result
            else:
                raise ValueError(f"No data returned for {symbol}")

        except Exception as e:
            print(f"Alpha Vantage error for {symbol}: {e}")
            # Fallback to yfinance
            return self._get_price_yfinance(symbol)

    def _get_price_yfinance(self, symbol):
        """Fallback method using yfinance"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period='1d')

            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
            else:
                current_price = info.get('currentPrice', info.get('previousClose', 0))

            result = {
                'symbol': symbol,
                'price': float(current_price),
                'change': 0,
                'change_percent': '0%',
                'volume': int(hist['Volume'].iloc[-1]) if not hist.empty else 0,
                'timestamp': datetime.now()
            }
            return result
        except Exception as e:
            raise ValueError(f"Could not fetch price for {symbol}: {e}")

    def get_intraday_data(self, symbol, interval='5min'):
        """
        Get intraday time series data.

        Parameters:
        -----------
        symbol : str
            Stock ticker symbol
        interval : str
            Time interval: 1min, 5min, 15min, 30min, 60min

        Returns:
        --------
        dict
            Intraday price data
        """
        cache_key = f"intraday_{symbol}_{interval}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        params = {
            'function': 'TIME_SERIES_INTRADAY',
            'symbol': symbol,
            'interval': interval,
            'apikey': self.api_key
        }

        data = self._make_request(params)
        self.cache.set(cache_key, data)
        return data

    def get_historical_volatility(self, symbol, period='1y'):
        """
        Calculate historical volatility from price data.

        Parameters:
        -----------
        symbol : str
            Stock ticker symbol
        period : str
            Historical period (e.g., '1y', '6mo', '3mo')

        Returns:
        --------
        float
            Annualized historical volatility
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)

            if hist.empty:
                raise ValueError("No historical data available")

            # Calculate log returns
            returns = hist['Close'].pct_change().dropna()

            # Annualized volatility (assuming 252 trading days)
            volatility = returns.std() * (252 ** 0.5)

            return volatility
        except Exception as e:
            print(f"Error calculating volatility for {symbol}: {e}")
            return 0.30  # Default 30% volatility


class YahooFinanceClient:
    """Client for Yahoo Finance data (free, unlimited)"""

    def __init__(self, cache_ttl=60):
        self.cache = MarketDataCache(ttl_seconds=cache_ttl)

    def get_stock_price(self, symbol):
        """Get current stock price"""
        cache_key = f"yf_quote_{symbol}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period='1d')

            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                volume = hist['Volume'].iloc[-1]
            else:
                current_price = info.get('currentPrice', info.get('previousClose', 0))
                volume = info.get('volume', 0)

            result = {
                'symbol': symbol,
                'price': float(current_price),
                'bid': float(info.get('bid', current_price)),
                'ask': float(info.get('ask', current_price)),
                'volume': int(volume),
                'timestamp': datetime.now()
            }

            self.cache.set(cache_key, result)
            return result

        except Exception as e:
            raise ValueError(f"Could not fetch price for {symbol}: {e}")

    def get_options_chain(self, symbol):
        """
        Get options chain data.

        Parameters:
        -----------
        symbol : str
            Stock ticker symbol

        Returns:
        --------
        dict
            Options chain data with calls and puts
        """
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options

            if not expirations:
                return {'error': 'No options data available'}

            # Get options for all expirations
            options_data = {
                'symbol': symbol,
                'expirations': list(expirations),
                'chains': {}
            }

            for expiry in expirations[:5]:  # Limit to first 5 expirations
                chain = ticker.option_chain(expiry)
                options_data['chains'][expiry] = {
                    'calls': chain.calls.to_dict('records'),
                    'puts': chain.puts.to_dict('records')
                }

            return options_data

        except Exception as e:
            raise ValueError(f"Could not fetch options chain for {symbol}: {e}")

    def get_historical_volatility(self, symbol, period='1y', window=30):
        """
        Calculate historical volatility.

        Parameters:
        -----------
        symbol : str
            Stock ticker symbol
        period : str
            Historical period
        window : int
            Rolling window for volatility calculation

        Returns:
        --------
        float
            Annualized historical volatility
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)

            if hist.empty:
                return 0.30

            # Calculate log returns
            returns = hist['Close'].pct_change().dropna()

            # Annualized volatility
            volatility = returns.std() * (252 ** 0.5)

            return volatility

        except Exception as e:
            print(f"Error calculating volatility: {e}")
            return 0.30

    def get_risk_free_rate(self):
        """
        Get current risk-free rate (using 10-year Treasury).

        Returns:
        --------
        float
            Risk-free rate
        """
        try:
            # ^TNX is the ticker for 10-year Treasury yield
            tnx = yf.Ticker("^TNX")
            hist = tnx.history(period='1d')

            if not hist.empty:
                # Convert from percentage to decimal
                rate = hist['Close'].iloc[-1] / 100
                return rate
            else:
                return 0.05  # Default 5%

        except Exception as e:
            print(f"Error fetching risk-free rate: {e}")
            return 0.05


class MarketDataManager:
    """
    Unified market data manager that handles multiple data sources.
    """

    def __init__(self, alpha_vantage_key=None, use_yfinance=True):
        self.av_client = AlphaVantageClient(alpha_vantage_key) if alpha_vantage_key else None
        self.yf_client = YahooFinanceClient() if use_yfinance else None
        self.preferred_source = 'yfinance' if use_yfinance else 'alphavantage'

    def get_stock_price(self, symbol):
        """Get stock price from preferred source with fallback"""
        if self.preferred_source == 'yfinance' and self.yf_client:
            try:
                return self.yf_client.get_stock_price(symbol)
            except Exception as e:
                print(f"YFinance failed: {e}, trying Alpha Vantage")
                if self.av_client:
                    return self.av_client.get_stock_price(symbol)
                raise
        elif self.av_client:
            return self.av_client.get_stock_price(symbol)
        else:
            raise ValueError("No market data source available")

    def get_options_chain(self, symbol):
        """Get options chain data"""
        if self.yf_client:
            return self.yf_client.get_options_chain(symbol)
        else:
            raise ValueError("Options chain only available via Yahoo Finance")

    def get_historical_volatility(self, symbol, period='1y'):
        """Get historical volatility"""
        if self.yf_client:
            return self.yf_client.get_historical_volatility(symbol, period)
        elif self.av_client:
            return self.av_client.get_historical_volatility(symbol, period)
        else:
            return 0.30  # Default

    def get_risk_free_rate(self):
        """Get risk-free rate"""
        if self.yf_client:
            return self.yf_client.get_risk_free_rate()
        else:
            return 0.05  # Default 5%
