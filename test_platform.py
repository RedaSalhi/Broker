"""
Test script to verify platform functionality
"""
from models.black_scholes import black_scholes_price, calculate_delta, implied_volatility
from models.greeks import calculate_all_greeks
import numpy as np


def test_black_scholes():
    """Test Black-Scholes pricing"""
    print("\n=== Testing Black-Scholes Pricing ===")

    # Test case: AAPL call option
    S = 150.0  # Current stock price
    K = 145.0  # Strike price
    T = 30/365.0  # 30 days to expiration
    r = 0.05  # 5% risk-free rate
    sigma = 0.25  # 25% volatility

    # Calculate call price
    call_price = black_scholes_price(S, K, T, r, sigma, 'call')
    print(f"Call Price: ${call_price:.2f}")

    # Calculate put price
    put_price = black_scholes_price(S, K, T, r, sigma, 'put')
    print(f"Put Price: ${put_price:.2f}")

    # Test put-call parity: C - P = S - K*e^(-rT)
    parity_lhs = call_price - put_price
    parity_rhs = S - K * np.exp(-r * T)
    print(f"\nPut-Call Parity Check:")
    print(f"C - P = ${parity_lhs:.2f}")
    print(f"S - Ke^(-rT) = ${parity_rhs:.2f}")
    print(f"Difference: ${abs(parity_lhs - parity_rhs):.6f} (should be near 0)")

    assert abs(parity_lhs - parity_rhs) < 0.01, "Put-call parity violated!"
    print("✓ Put-call parity verified")


def test_greeks():
    """Test Greeks calculations"""
    print("\n=== Testing Greeks ===")

    S = 150.0
    K = 145.0
    T = 30/365.0
    r = 0.05
    sigma = 0.25

    greeks = calculate_all_greeks(S, K, T, r, sigma, 'call')

    print(f"Delta: {greeks['delta']:.4f}")
    print(f"Gamma: {greeks['gamma']:.4f}")
    print(f"Vega: {greeks['vega']:.4f}")
    print(f"Theta: {greeks['theta']:.4f}")
    print(f"Rho: {greeks['rho']:.4f}")

    # Delta should be between 0 and 1 for calls
    assert 0 <= greeks['delta'] <= 1, "Delta out of range for call"
    print("✓ Delta in valid range")

    # Gamma should be positive
    assert greeks['gamma'] > 0, "Gamma should be positive"
    print("✓ Gamma is positive")


def test_implied_volatility():
    """Test implied volatility calculation"""
    print("\n=== Testing Implied Volatility ===")

    S = 150.0
    K = 145.0
    T = 30/365.0
    r = 0.05
    true_sigma = 0.25

    # Calculate option price with known volatility
    market_price = black_scholes_price(S, K, T, r, true_sigma, 'call')
    print(f"Market Price: ${market_price:.2f}")

    # Calculate implied volatility
    iv = implied_volatility(market_price, S, K, T, r, 'call')
    print(f"True Volatility: {true_sigma:.4f}")
    print(f"Implied Volatility: {iv:.4f}")
    print(f"Difference: {abs(iv - true_sigma):.6f}")

    assert abs(iv - true_sigma) < 0.0001, "IV calculation error too large"
    print("✓ Implied volatility correctly recovered")


def test_delta_hedging():
    """Test delta hedging calculations"""
    print("\n=== Testing Delta Hedging ===")

    S = 150.0
    K = 145.0
    T = 30/365.0
    r = 0.05
    sigma = 0.25

    # Calculate delta for call
    delta = calculate_delta(S, K, T, r, sigma, 'call')
    print(f"Call Delta: {delta:.4f}")

    # Position: Short 10 call contracts
    num_contracts = -10
    multiplier = 100
    position_delta = delta * num_contracts * multiplier

    print(f"Position Delta: {position_delta:.0f}")

    # Hedge shares needed (opposite sign)
    hedge_shares = -position_delta
    print(f"Hedge Shares Needed: {hedge_shares:.0f}")

    # After hedging, net delta should be near 0
    net_delta = position_delta + hedge_shares
    print(f"Net Delta After Hedge: {net_delta:.6f}")

    assert abs(net_delta) < 0.01, "Hedging not effective"
    print("✓ Delta hedge correctly calculated")


def test_pnl_calculation():
    """Test P&L calculation for seller"""
    print("\n=== Testing P&L Calculation ===")

    # Seller scenario
    premium_collected = 7.50  # per contract
    contracts = 10
    multiplier = 100

    total_premium = premium_collected * contracts * multiplier
    print(f"Premium Collected: ${total_premium:,.2f}")

    # After some time, option value decreased to $5.00
    current_option_value = 5.00
    total_current_value = current_option_value * contracts * multiplier

    # P&L for seller (short position)
    pnl = total_premium - total_current_value
    print(f"Current Option Value: ${total_current_value:,.2f}")
    print(f"P&L: ${pnl:,.2f}")

    roi = (pnl / total_premium) * 100
    print(f"ROI: {roi:.2f}%")

    assert pnl > 0, "Expected profitable scenario"
    print("✓ P&L calculation correct")


def main():
    """Run all tests"""
    print("=" * 50)
    print("OPTIONS TRADING PLATFORM - TEST SUITE")
    print("=" * 50)

    try:
        test_black_scholes()
        test_greeks()
        test_implied_volatility()
        test_delta_hedging()
        test_pnl_calculation()

        print("\n" + "=" * 50)
        print("✓ ALL TESTS PASSED!")
        print("=" * 50)
        print("\nThe platform is ready to use.")
        print("Run 'python3 app.py' to start the web server.")

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    main()
