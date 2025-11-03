"""
Greeks Calculator

Calculates option Greeks (sensitivities) for risk management and hedging.
Greeks measure how option prices change with respect to various factors.
"""
import numpy as np
from scipy.stats import norm


def calculate_all_greeks(S, K, T, r, sigma, option_type='call', q=0):
    """
    Calculate all Greeks for an option.

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
    dict
        Dictionary containing all Greeks: delta, gamma, vega, theta, rho
    """
    greeks = {
        'delta': delta(S, K, T, r, sigma, option_type, q),
        'gamma': gamma(S, K, T, r, sigma, q),
        'vega': vega(S, K, T, r, sigma, q),
        'theta': theta(S, K, T, r, sigma, option_type, q),
        'rho': rho(S, K, T, r, sigma, option_type, q)
    }
    return greeks


def delta(S, K, T, r, sigma, option_type='call', q=0):
    """
    Calculate Delta: ∂V/∂S

    Delta measures the rate of change of option value with respect to
    changes in the underlying asset's price.

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
        Delta value (between 0 and 1 for calls, -1 and 0 for puts)
    """
    if T <= 0:
        if option_type == 'call':
            return 1.0 if S > K else 0.0
        else:
            return -1.0 if S < K else 0.0

    d1 = (np.log(S / K) + (r - q + sigma**2 / 2) * T) / (sigma * np.sqrt(T))

    if option_type == 'call':
        return np.exp(-q * T) * norm.cdf(d1)
    else:  # put
        return np.exp(-q * T) * (norm.cdf(d1) - 1)


def gamma(S, K, T, r, sigma, q=0):
    """
    Calculate Gamma: ∂²V/∂S²

    Gamma measures the rate of change of delta with respect to changes
    in the underlying price. Same for calls and puts.

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
    q : float
        Dividend yield

    Returns:
    --------
    float
        Gamma value
    """
    if T <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r - q + sigma**2 / 2) * T) / (sigma * np.sqrt(T))

    gamma_value = (np.exp(-q * T) * norm.pdf(d1)) / (S * sigma * np.sqrt(T))

    return gamma_value


def vega(S, K, T, r, sigma, q=0):
    """
    Calculate Vega: ∂V/∂σ

    Vega measures sensitivity to volatility changes.
    Same for calls and puts.

    Note: Vega is typically expressed as the change in option value
    for a 1% change in volatility, so we divide by 100.

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
    q : float
        Dividend yield

    Returns:
    --------
    float
        Vega value (per 1% change in volatility)
    """
    if T <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r - q + sigma**2 / 2) * T) / (sigma * np.sqrt(T))

    vega_value = S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T)

    # Return vega per 1% change in volatility
    return vega_value / 100


def theta(S, K, T, r, sigma, option_type='call', q=0):
    """
    Calculate Theta: ∂V/∂t

    Theta measures the rate of time decay of the option value.
    Expressed as the change in value per day (divided by 365).

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
        Theta value (per day)
    """
    if T <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r - q + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    # Common term
    term1 = -(S * np.exp(-q * T) * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))

    if option_type == 'call':
        term2 = q * S * np.exp(-q * T) * norm.cdf(d1)
        term3 = -r * K * np.exp(-r * T) * norm.cdf(d2)
        theta_value = term1 + term2 + term3
    else:  # put
        term2 = -q * S * np.exp(-q * T) * norm.cdf(-d1)
        term3 = r * K * np.exp(-r * T) * norm.cdf(-d2)
        theta_value = term1 + term2 + term3

    # Return theta per day
    return theta_value / 365


def rho(S, K, T, r, sigma, option_type='call', q=0):
    """
    Calculate Rho: ∂V/∂r

    Rho measures sensitivity to interest rate changes.
    Expressed as the change in value for a 1% change in interest rate.

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
        Rho value (per 1% change in interest rate)
    """
    if T <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r - q + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    if option_type == 'call':
        rho_value = K * T * np.exp(-r * T) * norm.cdf(d2)
    else:  # put
        rho_value = -K * T * np.exp(-r * T) * norm.cdf(-d2)

    # Return rho per 1% change in interest rate
    return rho_value / 100


def lambda_greek(S, K, T, r, sigma, option_type='call', q=0):
    """
    Calculate Lambda (Omega): Leverage/Elasticity

    Lambda measures the percentage change in option value per
    percentage change in underlying price.

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
        Lambda value
    """
    from models.black_scholes import black_scholes_price

    option_price = black_scholes_price(S, K, T, r, sigma, option_type, q)

    if option_price == 0:
        return 0.0

    delta_value = delta(S, K, T, r, sigma, option_type, q)

    lambda_value = delta_value * (S / option_price)

    return lambda_value


def portfolio_greeks(positions):
    """
    Calculate portfolio-level Greeks.

    Parameters:
    -----------
    positions : list of dict
        List of position dictionaries with keys:
        - quantity: number of contracts (positive for long, negative for short)
        - S, K, T, r, sigma, option_type, q: option parameters

    Returns:
    --------
    dict
        Portfolio Greeks
    """
    portfolio = {
        'delta': 0,
        'gamma': 0,
        'vega': 0,
        'theta': 0,
        'rho': 0
    }

    for position in positions:
        quantity = position['quantity']
        greeks = calculate_all_greeks(
            S=position['S'],
            K=position['K'],
            T=position['T'],
            r=position['r'],
            sigma=position['sigma'],
            option_type=position['option_type'],
            q=position.get('q', 0)
        )

        # Aggregate Greeks (weighted by position size)
        for greek in portfolio:
            portfolio[greek] += greeks[greek] * quantity

    return portfolio


def risk_report(S, K, T, r, sigma, option_type='call', q=0, position_size=1):
    """
    Generate a comprehensive risk report for an option position.

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
    position_size : int
        Number of contracts

    Returns:
    --------
    dict
        Comprehensive risk metrics
    """
    from models.black_scholes import black_scholes_price

    greeks = calculate_all_greeks(S, K, T, r, sigma, option_type, q)
    option_price = black_scholes_price(S, K, T, r, sigma, option_type, q)

    # Calculate position-level metrics
    multiplier = 100  # Standard options multiplier

    report = {
        'option_price': option_price,
        'position_value': option_price * position_size * multiplier,
        'greeks': greeks,
        'position_delta': greeks['delta'] * position_size * multiplier,
        'position_gamma': greeks['gamma'] * position_size * multiplier,
        'position_vega': greeks['vega'] * position_size * multiplier,
        'position_theta': greeks['theta'] * position_size * multiplier,
        'position_rho': greeks['rho'] * position_size * multiplier,
        'moneyness': S / K,
        'time_to_expiry_days': T * 365,
        'leverage': lambda_greek(S, K, T, r, sigma, option_type, q)
    }

    return report
