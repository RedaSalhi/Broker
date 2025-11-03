"""
Delta Hedging Module

Implements delta hedging strategies to neutralize directional risk
from options positions.
"""
from datetime import datetime, date
from models.greeks import delta
from data.database import db, Position, Hedge, Trade
import config


class DeltaHedger:
    """Delta hedging manager"""

    def __init__(self, market_data_manager, multiplier=100):
        self.market_data = market_data_manager
        self.multiplier = multiplier
        self.rehedge_threshold = config.REHEDGE_THRESHOLD
        self.commission_per_share = config.STOCK_COMMISSION

    def calculate_hedge_requirements(self, position):
        """
        Calculate required hedge for a position.

        Parameters:
        -----------
        position : Position
            Position to hedge

        Returns:
        --------
        dict
            Hedge requirements including shares needed, cost, etc.
        """
        # Get current market data
        market_data = self.market_data.get_stock_price(position.symbol)
        current_price = market_data['price']

        # Calculate time to expiration
        days_to_expiry = (position.expiration - date.today()).days
        T = max(days_to_expiry / 365.0, 0.0001)

        # Calculate option delta
        option_delta = delta(
            S=current_price,
            K=position.strike,
            T=T,
            r=position.risk_free_rate,
            sigma=position.implied_vol,
            option_type=position.option_type,
            q=position.dividend_yield
        )

        # Calculate position delta (total exposure)
        position_delta = option_delta * position.quantity * self.multiplier

        # Calculate current hedge
        current_hedge_shares = sum(h.hedge_quantity for h in position.hedges)

        # Delta after current hedge
        net_delta = position_delta + current_hedge_shares

        # Required additional hedge to neutralize delta
        required_hedge_shares = -net_delta

        # Calculate costs
        hedge_value = abs(required_hedge_shares) * current_price
        commission = abs(required_hedge_shares) * self.commission_per_share
        spread_cost = hedge_value * config.BID_ASK_SPREAD / 2

        total_cost = commission + spread_cost

        return {
            'symbol': position.symbol,
            'position_id': position.id,
            'option_delta': option_delta,
            'position_delta': position_delta,
            'current_hedge_shares': current_hedge_shares,
            'net_delta': net_delta,
            'required_hedge_shares': required_hedge_shares,
            'underlying_price': current_price,
            'hedge_value': hedge_value,
            'commission': commission,
            'spread_cost': spread_cost,
            'total_cost': total_cost,
            'should_rehedge': abs(net_delta / position_delta) > self.rehedge_threshold if position_delta != 0 else False
        }

    def execute_hedge(self, position, hedge_shares=None, hedge_type='initial'):
        """
        Execute a delta hedge.

        Parameters:
        -----------
        position : Position
            Position to hedge
        hedge_shares : float
            Number of shares to hedge (if None, will calculate)
        hedge_type : str
            'initial', 'rebalance', or 'close'

        Returns:
        --------
        Hedge
            Created hedge record
        """
        # Calculate hedge requirements
        hedge_req = self.calculate_hedge_requirements(position)

        # Use provided shares or calculated requirement
        if hedge_shares is None:
            hedge_shares = hedge_req['required_hedge_shares']

        # Get current price
        market_data = self.market_data.get_stock_price(position.symbol)
        current_price = market_data['price']

        # Calculate transaction cost
        commission = abs(hedge_shares) * self.commission_per_share
        hedge_value = abs(hedge_shares) * current_price
        spread_cost = hedge_value * config.BID_ASK_SPREAD / 2
        total_cost = commission + spread_cost

        # Create hedge record
        hedge = Hedge(
            position_id=position.id,
            hedge_quantity=hedge_shares,
            hedge_price=current_price,
            transaction_cost=total_cost,
            delta_before=hedge_req['net_delta'],
            delta_after=hedge_req['net_delta'] + hedge_shares,
            underlying_price=current_price,
            hedge_type=hedge_type
        )

        db.session.add(hedge)

        # Create trade record
        trade = Trade(
            position_id=position.id,
            trade_type='hedge_stock',
            symbol=position.symbol,
            quantity=hedge_shares,
            price=current_price,
            commission=total_cost,
            notes=f"Delta hedge ({hedge_type})"
        )

        db.session.add(trade)
        db.session.commit()

        return hedge

    def check_rehedge_needed(self, position_id):
        """
        Check if a position needs rehedging.

        Parameters:
        -----------
        position_id : int
            Position ID to check

        Returns:
        --------
        dict
            Rehedge assessment
        """
        position = Position.query.get(position_id)
        if not position or position.status != 'open':
            return {'needed': False, 'reason': 'Position not open'}

        hedge_req = self.calculate_hedge_requirements(position)

        return {
            'needed': hedge_req['should_rehedge'],
            'net_delta': hedge_req['net_delta'],
            'position_delta': hedge_req['position_delta'],
            'threshold': self.rehedge_threshold,
            'delta_ratio': abs(hedge_req['net_delta'] / hedge_req['position_delta']) if hedge_req['position_delta'] != 0 else 0,
            'required_shares': hedge_req['required_hedge_shares'],
            'cost': hedge_req['total_cost']
        }

    def get_portfolio_delta_exposure(self):
        """
        Calculate total portfolio delta exposure.

        Returns:
        --------
        dict
            Portfolio delta metrics
        """
        open_positions = Position.query.filter_by(status='open').all()

        total_delta = 0
        total_hedge_value = 0
        positions_needing_hedge = []

        for position in open_positions:
            try:
                hedge_req = self.calculate_hedge_requirements(position)

                total_delta += hedge_req['net_delta']

                if hedge_req['should_rehedge']:
                    positions_needing_hedge.append({
                        'position_id': position.id,
                        'symbol': position.symbol,
                        'net_delta': hedge_req['net_delta'],
                        'required_shares': hedge_req['required_hedge_shares'],
                        'cost': hedge_req['total_cost']
                    })

                # Calculate total hedge value
                for hedge in position.hedges:
                    total_hedge_value += abs(hedge.hedge_quantity * hedge.hedge_price)

            except Exception as e:
                print(f"Error calculating delta for position {position.id}: {e}")
                continue

        return {
            'total_portfolio_delta': total_delta,
            'total_hedge_value': total_hedge_value,
            'positions_needing_rehedge': len(positions_needing_hedge),
            'rehedge_details': positions_needing_hedge
        }

    def auto_rehedge_portfolio(self, execute=False):
        """
        Automatically rehedge all positions that exceed threshold.

        Parameters:
        -----------
        execute : bool
            If True, execute hedges; if False, only return recommendations

        Returns:
        --------
        dict
            Rehedge summary
        """
        open_positions = Position.query.filter_by(status='open').all()

        recommendations = []
        executed = []

        for position in open_positions:
            try:
                rehedge_check = self.check_rehedge_needed(position.id)

                if rehedge_check['needed']:
                    rec = {
                        'position_id': position.id,
                        'symbol': position.symbol,
                        'required_shares': rehedge_check['required_shares'],
                        'cost': rehedge_check['cost'],
                        'net_delta': rehedge_check['net_delta']
                    }

                    recommendations.append(rec)

                    if execute:
                        hedge = self.execute_hedge(position, hedge_type='rebalance')
                        executed.append({
                            'position_id': position.id,
                            'hedge_id': hedge.id,
                            'shares': hedge.hedge_quantity,
                            'cost': hedge.transaction_cost
                        })

            except Exception as e:
                print(f"Error rehedging position {position.id}: {e}")
                continue

        return {
            'recommendations': recommendations,
            'executed': executed if execute else [],
            'total_recommendations': len(recommendations),
            'total_executed': len(executed) if execute else 0,
            'total_cost': sum(e['cost'] for e in executed) if execute else 0
        }

    def calculate_hedging_pnl(self, position_id):
        """
        Calculate P&L from hedging activities.

        Parameters:
        -----------
        position_id : int
            Position ID

        Returns:
        --------
        dict
            Hedging P&L breakdown
        """
        position = Position.query.get(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        # Get current underlying price
        market_data = self.market_data.get_stock_price(position.symbol)
        current_price = market_data['price']

        total_hedge_pnl = 0
        total_costs = 0
        total_shares = 0

        hedge_details = []

        for hedge in position.hedges:
            # P&L from this hedge
            hedge_pnl = hedge.hedge_quantity * (current_price - hedge.hedge_price)
            total_hedge_pnl += hedge_pnl
            total_costs += hedge.transaction_cost
            total_shares += hedge.hedge_quantity

            hedge_details.append({
                'hedge_id': hedge.id,
                'shares': hedge.hedge_quantity,
                'entry_price': hedge.hedge_price,
                'current_price': current_price,
                'pnl': hedge_pnl,
                'cost': hedge.transaction_cost,
                'date': hedge.hedge_date
            })

        net_hedge_pnl = total_hedge_pnl - total_costs

        return {
            'position_id': position_id,
            'symbol': position.symbol,
            'total_hedge_shares': total_shares,
            'total_hedge_pnl': total_hedge_pnl,
            'total_costs': total_costs,
            'net_hedge_pnl': net_hedge_pnl,
            'current_price': current_price,
            'hedge_details': hedge_details
        }

    def get_hedging_efficiency(self, position_id):
        """
        Calculate hedging efficiency metrics.

        Parameters:
        -----------
        position_id : int
            Position ID

        Returns:
        --------
        dict
            Efficiency metrics
        """
        position = Position.query.get(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        # Get hedge requirements
        hedge_req = self.calculate_hedge_requirements(position)

        # Calculate efficiency
        if hedge_req['position_delta'] != 0:
            hedge_ratio = abs(hedge_req['current_hedge_shares'] / (hedge_req['position_delta'] / hedge_req['option_delta']))
            delta_neutrality = 1 - abs(hedge_req['net_delta'] / hedge_req['position_delta'])
        else:
            hedge_ratio = 0
            delta_neutrality = 0

        # Get hedging costs as % of position value
        total_costs = sum(h.transaction_cost for h in position.hedges)
        position_value = abs(position.premium_collected * position.quantity * self.multiplier)
        cost_ratio = (total_costs / position_value * 100) if position_value > 0 else 0

        return {
            'position_id': position_id,
            'symbol': position.symbol,
            'hedge_ratio': hedge_ratio,
            'delta_neutrality': delta_neutrality,
            'cost_ratio': cost_ratio,
            'total_rehedges': position.hedges.count(),
            'net_delta': hedge_req['net_delta'],
            'position_delta': hedge_req['position_delta']
        }
