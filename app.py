"""
Options Trading Platform - Main Flask Application

A comprehensive options trading platform with Black-Scholes pricing,
delta hedging, and P&L tracking for market makers.
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from datetime import datetime, date
import config
from data.database import db, init_db, Position, get_portfolio_summary
from data.market_data import MarketDataManager
from models.black_scholes import black_scholes_price, calculate_delta, implied_volatility
from models.greeks import calculate_all_greeks, risk_report
from models.portfolio import Portfolio
from utils.hedging import DeltaHedger
from utils.pnl import PnLTracker

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
CORS(app)

# Initialize services
market_data = MarketDataManager(
    alpha_vantage_key=config.ALPHA_VANTAGE_API_KEY,
    use_yfinance=True
)
portfolio = Portfolio(market_data)
hedger = DeltaHedger(market_data)
pnl_tracker = PnLTracker(market_data)

# Initialize database
init_db(app)


@app.route('/')
def index():
    """Main dashboard"""
    return render_template('dashboard.html')


@app.route('/api/price-option', methods=['POST'])
def price_option():
    """
    Calculate option price using Black-Scholes.

    Expected JSON:
    {
        "symbol": "AAPL",
        "strike": 150,
        "days_to_expiry": 30,
        "option_type": "call",
        "implied_vol": 0.25,
        "num_contracts": 1
    }
    """
    try:
        data = request.json

        # Fetch current market price
        stock_data = market_data.get_stock_price(data['symbol'])
        current_price = stock_data['price']

        # Get risk-free rate
        risk_free_rate = market_data.get_risk_free_rate()

        # Calculate time to expiration
        T = data['days_to_expiry'] / 365.0

        # If IV not provided, use historical volatility
        sigma = data.get('implied_vol')
        if sigma is None:
            sigma = market_data.get_historical_volatility(data['symbol'])

        # Calculate option price
        option_price = black_scholes_price(
            S=current_price,
            K=data['strike'],
            T=T,
            r=risk_free_rate,
            sigma=sigma,
            option_type=data['option_type'],
            q=data.get('dividend_yield', 0)
        )

        # Calculate Greeks
        greeks = calculate_all_greeks(
            S=current_price,
            K=data['strike'],
            T=T,
            r=risk_free_rate,
            sigma=sigma,
            option_type=data['option_type'],
            q=data.get('dividend_yield', 0)
        )

        # Calculate hedge requirements
        num_contracts = data.get('num_contracts', 1)
        position_delta = greeks['delta'] * num_contracts * config.OPTIONS_MULTIPLIER
        hedge_shares = -position_delta  # Negative to offset

        return jsonify({
            'success': True,
            'symbol': data['symbol'],
            'current_price': current_price,
            'option_price': round(option_price, 2),
            'total_premium': round(option_price * num_contracts * config.OPTIONS_MULTIPLIER, 2),
            'greeks': {
                'delta': round(greeks['delta'], 4),
                'gamma': round(greeks['gamma'], 4),
                'vega': round(greeks['vega'], 4),
                'theta': round(greeks['theta'], 4),
                'rho': round(greeks['rho'], 4)
            },
            'hedge_shares': round(hedge_shares, 2),
            'hedge_value': round(hedge_shares * current_price, 2),
            'implied_vol': round(sigma, 4),
            'risk_free_rate': round(risk_free_rate, 4)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/calculate-iv', methods=['POST'])
def calculate_iv():
    """
    Calculate implied volatility from market price.

    Expected JSON:
    {
        "symbol": "AAPL",
        "strike": 150,
        "days_to_expiry": 30,
        "option_type": "call",
        "market_price": 5.50
    }
    """
    try:
        data = request.json

        # Fetch current market price
        stock_data = market_data.get_stock_price(data['symbol'])
        current_price = stock_data['price']

        # Get risk-free rate
        risk_free_rate = market_data.get_risk_free_rate()

        # Calculate time to expiration
        T = data['days_to_expiry'] / 365.0

        # Calculate implied volatility
        iv = implied_volatility(
            market_price=data['market_price'],
            S=current_price,
            K=data['strike'],
            T=T,
            r=risk_free_rate,
            option_type=data['option_type'],
            q=data.get('dividend_yield', 0)
        )

        return jsonify({
            'success': True,
            'implied_volatility': round(iv, 4),
            'current_price': current_price
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/sell-option', methods=['POST'])
def sell_option():
    """
    Execute option sale and create position.

    Expected JSON:
    {
        "symbol": "AAPL",
        "option_type": "call",
        "strike": 150,
        "expiration": "2024-12-20",
        "quantity": -10,
        "premium": 5.50,
        "implied_vol": 0.25
    }
    """
    try:
        data = request.json

        # Parse expiration date
        exp_date = datetime.strptime(data['expiration'], '%Y-%m-%d').date()

        # Create position
        position = portfolio.add_position(
            symbol=data['symbol'],
            option_type=data['option_type'],
            strike=data['strike'],
            expiration=exp_date,
            quantity=data['quantity'],
            premium=data['premium'],
            implied_vol=data.get('implied_vol'),
            dividend_yield=data.get('dividend_yield', 0)
        )

        return jsonify({
            'success': True,
            'position_id': position.id,
            'message': f"Position created successfully",
            'position': position.to_dict()
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/calculate-hedge', methods=['POST'])
def calculate_hedge():
    """
    Calculate hedge requirements for a position.

    Expected JSON:
    {
        "position_id": 1
    }
    """
    try:
        data = request.json
        position_id = data['position_id']

        hedge_req = hedger.calculate_hedge_requirements(
            Position.query.get(position_id)
        )

        return jsonify({
            'success': True,
            'hedge_requirements': hedge_req
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/execute-hedge', methods=['POST'])
def execute_hedge():
    """
    Execute delta hedge for a position.

    Expected JSON:
    {
        "position_id": 1,
        "hedge_shares": -500 (optional)
    }
    """
    try:
        data = request.json
        position_id = data['position_id']
        hedge_shares = data.get('hedge_shares')

        position = Position.query.get(position_id)
        if not position:
            return jsonify({'success': False, 'error': 'Position not found'}), 404

        # Execute hedge
        hedge = hedger.execute_hedge(
            position=position,
            hedge_shares=hedge_shares,
            hedge_type=data.get('hedge_type', 'initial')
        )

        return jsonify({
            'success': True,
            'message': 'Hedge executed successfully',
            'hedge': hedge.to_dict()
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/positions')
def get_positions():
    """Get all positions"""
    try:
        summary = portfolio.get_positions_summary()
        return jsonify({
            'success': True,
            'summary': summary
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/position/<int:position_id>')
def get_position(position_id):
    """Get specific position details"""
    try:
        position = Position.query.get(position_id)
        if not position:
            return jsonify({'success': False, 'error': 'Position not found'}), 404

        pnl = pnl_tracker.calculate_position_pnl(position_id)

        return jsonify({
            'success': True,
            'position': position.to_dict(),
            'pnl': pnl
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/close-position', methods=['POST'])
def close_position():
    """
    Close a position.

    Expected JSON:
    {
        "position_id": 1,
        "close_price": 3.50 (optional)
    }
    """
    try:
        data = request.json
        position_id = data['position_id']
        close_price = data.get('close_price')

        final_pnl = portfolio.close_position(position_id, close_price)

        return jsonify({
            'success': True,
            'message': 'Position closed successfully',
            'final_pnl': final_pnl
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/portfolio-greeks')
def get_portfolio_greeks():
    """Get portfolio-level Greeks"""
    try:
        greeks = portfolio.get_portfolio_greeks()
        return jsonify({
            'success': True,
            'greeks': greeks
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/portfolio-pnl')
def get_portfolio_pnl():
    """Get portfolio P&L"""
    try:
        pnl = pnl_tracker.get_portfolio_pnl()
        return jsonify({
            'success': True,
            'pnl': pnl
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/delta-exposure')
def get_delta_exposure():
    """Get portfolio delta exposure"""
    try:
        exposure = hedger.get_portfolio_delta_exposure()
        return jsonify({
            'success': True,
            'exposure': exposure
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/auto-rehedge', methods=['POST'])
def auto_rehedge():
    """
    Auto-rehedge portfolio.

    Expected JSON:
    {
        "execute": true/false
    }
    """
    try:
        data = request.json
        execute = data.get('execute', False)

        result = hedger.auto_rehedge_portfolio(execute=execute)

        return jsonify({
            'success': True,
            'result': result
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/market-data/<symbol>')
def get_market_data(symbol):
    """Get real-time market data for a symbol"""
    try:
        data = market_data.get_stock_price(symbol)
        vol = market_data.get_historical_volatility(symbol)

        return jsonify({
            'success': True,
            'data': {
                **data,
                'historical_volatility': round(vol, 4)
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/options-chain/<symbol>')
def get_options_chain(symbol):
    """Get options chain for a symbol"""
    try:
        chain = market_data.get_options_chain(symbol)
        return jsonify({
            'success': True,
            'chain': chain
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/performance-metrics')
def get_performance_metrics():
    """Get portfolio performance metrics"""
    try:
        metrics = pnl_tracker.get_performance_metrics()
        return jsonify({
            'success': True,
            'metrics': metrics
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/pnl-history')
def get_pnl_history():
    """Get P&L history"""
    try:
        position_id = request.args.get('position_id', type=int)
        days = request.args.get('days', default=30, type=int)

        history = pnl_tracker.get_pnl_history(position_id=position_id, days=days)

        return jsonify({
            'success': True,
            'history': history
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/positions')
def positions_page():
    """Positions view page"""
    return render_template('positions.html')


@app.route('/analytics')
def analytics_page():
    """Analytics dashboard page"""
    return render_template('analytics.html')


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )
