"""
Database Models

SQLAlchemy models for storing positions, trades, hedges, and market data.
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import func

db = SQLAlchemy()


class Position(db.Model):
    """Options positions (sold/bought)"""
    __tablename__ = 'positions'

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False, index=True)
    option_type = db.Column(db.String(4), nullable=False)  # 'call' or 'put'
    strike = db.Column(db.Float, nullable=False)
    expiration = db.Column(db.Date, nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)  # Positive for long, negative for short
    premium_collected = db.Column(db.Float)  # Premium per contract
    entry_price = db.Column(db.Float, nullable=False)  # Underlying price at entry
    entry_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    status = db.Column(db.String(10), default='open')  # 'open', 'closed', 'expired'
    close_date = db.Column(db.DateTime)
    close_price = db.Column(db.Float)  # Option price at close
    implied_vol = db.Column(db.Float)  # IV at entry
    risk_free_rate = db.Column(db.Float, default=0.05)
    dividend_yield = db.Column(db.Float, default=0.0)

    # Relationships
    hedges = db.relationship('Hedge', backref='position', lazy='dynamic', cascade='all, delete-orphan')
    pnl_snapshots = db.relationship('PnLSnapshot', backref='position', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Position {self.symbol} {self.option_type} {self.strike} exp:{self.expiration}>'

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'option_type': self.option_type,
            'strike': self.strike,
            'expiration': self.expiration.isoformat() if self.expiration else None,
            'quantity': self.quantity,
            'premium_collected': self.premium_collected,
            'entry_price': self.entry_price,
            'entry_date': self.entry_date.isoformat() if self.entry_date else None,
            'status': self.status,
            'close_date': self.close_date.isoformat() if self.close_date else None,
            'close_price': self.close_price,
            'implied_vol': self.implied_vol,
            'risk_free_rate': self.risk_free_rate,
            'dividend_yield': self.dividend_yield
        }


class Hedge(db.Model):
    """Delta hedges for positions"""
    __tablename__ = 'hedges'

    id = db.Column(db.Integer, primary_key=True)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'), nullable=False, index=True)
    hedge_quantity = db.Column(db.Float, nullable=False)  # Number of shares
    hedge_price = db.Column(db.Float, nullable=False)  # Price per share
    hedge_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    transaction_cost = db.Column(db.Float, default=0.0)  # Commissions + slippage
    delta_before = db.Column(db.Float)  # Delta before hedge
    delta_after = db.Column(db.Float)  # Delta after hedge
    underlying_price = db.Column(db.Float)  # Stock price at hedge
    hedge_type = db.Column(db.String(10), default='initial')  # 'initial', 'rebalance', 'close'

    def __repr__(self):
        return f'<Hedge pos:{self.position_id} qty:{self.hedge_quantity} @{self.hedge_price}>'

    def to_dict(self):
        return {
            'id': self.id,
            'position_id': self.position_id,
            'hedge_quantity': self.hedge_quantity,
            'hedge_price': self.hedge_price,
            'hedge_date': self.hedge_date.isoformat() if self.hedge_date else None,
            'transaction_cost': self.transaction_cost,
            'delta_before': self.delta_before,
            'delta_after': self.delta_after,
            'underlying_price': self.underlying_price,
            'hedge_type': self.hedge_type
        }


class PnLSnapshot(db.Model):
    """P&L snapshots over time"""
    __tablename__ = 'pnl_snapshots'

    id = db.Column(db.Integer, primary_key=True)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'), nullable=False, index=True)
    snapshot_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    underlying_price = db.Column(db.Float, nullable=False)
    option_price = db.Column(db.Float, nullable=False)
    delta = db.Column(db.Float)
    gamma = db.Column(db.Float)
    vega = db.Column(db.Float)
    theta = db.Column(db.Float)
    unrealized_pnl = db.Column(db.Float)
    realized_pnl = db.Column(db.Float, default=0.0)
    total_pnl = db.Column(db.Float)

    def __repr__(self):
        return f'<PnLSnapshot pos:{self.position_id} pnl:{self.total_pnl}>'

    def to_dict(self):
        return {
            'id': self.id,
            'position_id': self.position_id,
            'snapshot_date': self.snapshot_date.isoformat() if self.snapshot_date else None,
            'underlying_price': self.underlying_price,
            'option_price': self.option_price,
            'delta': self.delta,
            'gamma': self.gamma,
            'vega': self.vega,
            'theta': self.theta,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'total_pnl': self.total_pnl
        }


class MarketDataCache(db.Model):
    """Cache for market data"""
    __tablename__ = 'market_data_cache'

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    bid = db.Column(db.Float)
    ask = db.Column(db.Float)
    volume = db.Column(db.BigInteger)
    implied_vol = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<MarketData {self.symbol} @{self.price}>'

    def to_dict(self):
        return {
            'symbol': self.symbol,
            'price': self.price,
            'bid': self.bid,
            'ask': self.ask,
            'volume': self.volume,
            'implied_vol': self.implied_vol,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


class Trade(db.Model):
    """Trade execution log"""
    __tablename__ = 'trades'

    id = db.Column(db.Integer, primary_key=True)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'), index=True)
    trade_type = db.Column(db.String(20), nullable=False)  # 'sell_option', 'buy_option', 'hedge_stock'
    symbol = db.Column(db.String(10), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    commission = db.Column(db.Float, default=0.0)
    trade_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    notes = db.Column(db.Text)

    def __repr__(self):
        return f'<Trade {self.trade_type} {self.symbol} qty:{self.quantity}>'

    def to_dict(self):
        return {
            'id': self.id,
            'position_id': self.position_id,
            'trade_type': self.trade_type,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'price': self.price,
            'commission': self.commission,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'notes': self.notes
        }


class RiskLimit(db.Model):
    """Risk management limits"""
    __tablename__ = 'risk_limits'

    id = db.Column(db.Integer, primary_key=True)
    limit_type = db.Column(db.String(50), nullable=False, unique=True)  # 'max_delta', 'max_vega', etc.
    limit_value = db.Column(db.Float, nullable=False)
    current_value = db.Column(db.Float, default=0.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    breach_count = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<RiskLimit {self.limit_type}: {self.current_value}/{self.limit_value}>'

    def to_dict(self):
        return {
            'id': self.id,
            'limit_type': self.limit_type,
            'limit_value': self.limit_value,
            'current_value': self.current_value,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'breach_count': self.breach_count,
            'utilization': (self.current_value / self.limit_value * 100) if self.limit_value else 0
        }


def init_db(app):
    """Initialize database with app context"""
    db.init_app(app)
    with app.app_context():
        db.create_all()
        # Initialize default risk limits if they don't exist
        if RiskLimit.query.count() == 0:
            default_limits = [
                RiskLimit(limit_type='max_delta_exposure', limit_value=10000),
                RiskLimit(limit_type='max_vega_exposure', limit_value=5000),
                RiskLimit(limit_type='max_position_size', limit_value=100),
                RiskLimit(limit_type='max_concentration', limit_value=0.30)
            ]
            db.session.add_all(default_limits)
            db.session.commit()
            print("Database initialized with default risk limits")


def get_portfolio_summary():
    """Get summary of all open positions"""
    open_positions = Position.query.filter_by(status='open').all()

    summary = {
        'total_positions': len(open_positions),
        'total_value': 0,
        'positions_by_symbol': {},
        'positions_by_type': {'call': 0, 'put': 0},
        'expiring_soon': []
    }

    for pos in open_positions:
        # Count by type
        summary['positions_by_type'][pos.option_type] += abs(pos.quantity)

        # Group by symbol
        if pos.symbol not in summary['positions_by_symbol']:
            summary['positions_by_symbol'][pos.symbol] = 0
        summary['positions_by_symbol'][pos.symbol] += abs(pos.quantity)

        # Check expiring soon (within 7 days)
        days_to_expiry = (pos.expiration - datetime.now().date()).days
        if days_to_expiry <= 7:
            summary['expiring_soon'].append({
                'id': pos.id,
                'symbol': pos.symbol,
                'expiration': pos.expiration,
                'days': days_to_expiry
            })

    return summary
