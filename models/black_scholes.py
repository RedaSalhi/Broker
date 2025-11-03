"""
Black-Scholes Option Pricing Model

Implements the Black-Scholes formula for European options pricing
and implied volatility calculation.
"""
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq


def black_scholes_price(S, K, T, r, sigma, option_type='call', q=0):
    """
    Calculate option price using Black-Scholes formula.

    Parameters:
    -----------
    S : float
        Current stock price
    K : float
        Strike price
    T : float
        Time to expiration in years
    r : float
        Risk-free interest rate (annualized)
    sigma : float
        Volatility (annualized)
    option_type : str
        'call' or 'put'
    q : float
        Dividend yield (annualized)

    Returns:
    --------
    float
        Option price
    """
    if T <= 0:
        # Handle expiration
        if option_type == 'call':
            return max(0, S - K)
        else:
            return max(0, K - S)

    if sigma <= 0:
        raise ValueError("Volatility must be positive")

    # Calculate d1 and d2
    d1 = (np.log(S / K) + (r - q + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    # Calculate option price
    if option_type == 'call':
        price = S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    elif option_type == 'put':
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)
    else:
        raise ValueError("option_type must be 'call' or 'put'")

    return price


def calculate_delta(S, K, T, r, sigma, option_type='call', q=0):
    """
    Calculate option delta (∂V/∂S).

    Delta represents the rate of change of option price with respect to
    the underlying asset price. Also used as the hedge ratio.

    Parameters:
    -----------
    S : float
        Current stock price
    K : float
        Strike price
    T : float
        Time to expiration in years
    r : float
        Risk-free interest rate
    sigma : float
        Volatility
    option_type : str
        'call' or 'put'
    q : float
        Dividend yield

    Returns:
    --------
    float
        Delta value
    """
    if T <= 0:
        if option_type == 'call':
            return 1.0 if S > K else 0.0
        else:
            return -1.0 if S < K else 0.0

    d1 = (np.log(S / K) + (r - q + sigma**2 / 2) * T) / (sigma * np.sqrt(T))

    if option_type == 'call':
        delta = np.exp(-q * T) * norm.cdf(d1)
    elif option_type == 'put':
        delta = np.exp(-q * T) * (norm.cdf(d1) - 1)
    else:
        raise ValueError("option_type must be 'call' or 'put'")

    return delta


def implied_volatility(market_price, S, K, T, r, option_type='call', q=0,
                       initial_sigma=0.3, max_iterations=100, tolerance=1e-6):
    """
    Calculate implied volatility using Newton-Raphson method.

    Parameters:
    -----------
    market_price : float
        Observed market price of the option
    S : float
        Current stock price
    K : float
        Strike price
    T : float
        Time to expiration in years
    r : float
        Risk-free interest rate
    option_type : str
        'call' or 'put'
    q : float
        Dividend yield
    initial_sigma : float
        Initial guess for volatility
    max_iterations : int
        Maximum number of iterations
    tolerance : float
        Convergence tolerance

    Returns:
    --------
    float
        Implied volatility
    """
    if T <= 0:
        raise ValueError("Cannot calculate IV for expired options")

    # Check for arbitrage bounds
    if option_type == 'call':
        intrinsic = max(0, S * np.exp(-q * T) - K * np.exp(-r * T))
        if market_price < intrinsic:
            raise ValueError("Market price below intrinsic value")
    else:
        intrinsic = max(0, K * np.exp(-r * T) - S * np.exp(-q * T))
        if market_price < intrinsic:
            raise ValueError("Market price below intrinsic value")

    # Use Brent's method for robust root finding
    def objective(sigma):
        try:
            return black_scholes_price(S, K, T, r, sigma, option_type, q) - market_price
        except:
            return float('inf')

    try:
        # Search between 0.01 and 5.0 (1% to 500% volatility)
        iv = brentq(objective, 0.01, 5.0, xtol=tolerance, maxiter=max_iterations)
        return iv
    except ValueError:
        # If Brent's method fails, try Newton-Raphson
        sigma = initial_sigma

        for i in range(max_iterations):
            # Calculate vega for Newton-Raphson step
            d1 = (np.log(S / K) + (r - q + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
            vega = S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T)

            if vega < 1e-10:
                raise ValueError("Vega too small, cannot converge")

            # Calculate price difference
            price_diff = black_scholes_price(S, K, T, r, sigma, option_type, q) - market_price

            # Check convergence
            if abs(price_diff) < tolerance:
                return sigma

            # Newton-Raphson update
            sigma = sigma - price_diff / vega

            # Ensure sigma stays positive
            if sigma <= 0:
                sigma = 0.01

        raise ValueError(f"Failed to converge after {max_iterations} iterations")


def _d1_d2(S, K, T, r, sigma, q=0):
    """
    Helper function to calculate d1 and d2.

    Returns:
    --------
    tuple
        (d1, d2)
    """
    d1 = (np.log(S / K) + (r - q + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return d1, d2


# Validation function
def validate_inputs(S, K, T, r, sigma):
    """
    Validate Black-Scholes input parameters.

    Raises:
    -------
    ValueError
        If any parameter is invalid
    """
    if S <= 0:
        raise ValueError("Stock price must be positive")
    if K <= 0:
        raise ValueError("Strike price must be positive")
    if T < 0:
        raise ValueError("Time to expiration cannot be negative")
    if sigma < 0:
        raise ValueError("Volatility cannot be negative")
