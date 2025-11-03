"""
P&L Tracking and Analysis

Tracks profit and loss for both option sellers and buyers,
including realized and unrealized P&L, attribution analysis,
and performance metrics.
"""
from datetime import datetime, date, timedelta
from models.black_scholes import black_scholes_price
from models.greeks import calculate_all_greeks
from data.database import db, Position, PnLSnapshot, Hedge, Trade
import pandas as pd


class PnLTracker:
    """P&L tracking and analysis"""

    def __init__(self, market_data_manager, multiplier=100):
        self.market_data = market_data_manager
        self.multiplier = multiplier

    def calculate_position_pnl(self, position_id):
        """
        Calculate comprehensive P&L for a position.

        Parameters:
        -----------
        position_id : int
            Position ID

        Returns:
        --------
        dict
            Detailed P&L breakdown
        """
        position = Position.query.get(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        # Get current market data
        market_data = self.market_data.get_stock_price(position.symbol)
        current_underlying_price = market_data['price']

        # Calculate current option price
        if position.status == 'open':
            days_to_expiry = (position.expiration - date.today()).days
            T = max(days_to_expiry / 365.0, 0)

            current_option_price = black_scholes_price(
                S=current_underlying_price,
                K=position.strike,
                T=T,
                r=position.risk_free_rate,
                sigma=position.implied_vol,
                option_type=position.option_type,
                q=position.dividend_yield
            )
        else:
            current_option_price = position.close_price or 0

        # Calculate option P&L
        if position.quantity < 0:  # Short position (seller)
            # Premium collected - current value
            option_pnl = (position.premium_collected + current_option_price) * abs(position.quantity) * self.multiplier
        else:  # Long position (buyer)
            # Current value - premium paid
            option_pnl = (current_option_price - abs(position.premium_collected)) * position.quantity * self.multiplier

        # Calculate hedge P&L
        total_hedge_pnl = 0
        total_hedge_costs = 0
        net_hedge_shares = 0

        for hedge in position.hedges:
            # P&L from stock position
            stock_pnl = hedge.hedge_quantity * (current_underlying_price - hedge.hedge_price)
            total_hedge_pnl += stock_pnl
            total_hedge_costs += hedge.transaction_cost
            net_hedge_shares += hedge.hedge_quantity

        # Greeks for risk analysis
        if position.status == 'open' and T > 0:
            greeks = calculate_all_greeks(
                S=current_underlying_price,
                K=position.strike,
                T=T,
                r=position.risk_free_rate,
                sigma=position.implied_vol,
                option_type=position.option_type,
                q=position.dividend_yield
            )
        else:
            greeks = {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'rho': 0}

        # Calculate total P&L
        unrealized_pnl = option_pnl + total_hedge_pnl
        realized_pnl = -total_hedge_costs
        total_pnl = unrealized_pnl + realized_pnl

        # Return on capital (for sellers)
        if position.quantity < 0:
            initial_premium = abs(position.premium_collected) * abs(position.quantity) * self.multiplier
            roi = (total_pnl / initial_premium * 100) if initial_premium > 0 else 0
        else:
            initial_cost = abs(position.premium_collected) * position.quantity * self.multiplier
            roi = (total_pnl / initial_cost * 100) if initial_cost > 0 else 0

        return {
            'position_id': position_id,
            'symbol': position.symbol,
            'option_type': position.option_type,
            'strike': position.strike,
            'quantity': position.quantity,
            'status': position.status,
            'entry_date': position.entry_date,
            'expiration': position.expiration,
            'days_held': (datetime.now() - position.entry_date).days,
            'current_underlying_price': current_underlying_price,
            'entry_underlying_price': position.entry_price,
            'underlying_change': current_underlying_price - position.entry_price,
            'underlying_change_pct': ((current_underlying_price / position.entry_price - 1) * 100) if position.entry_price > 0 else 0,
            'current_option_price': current_option_price,
            'entry_option_price': abs(position.premium_collected),
            'option_pnl': option_pnl,
            'hedge_pnl': total_hedge_pnl,
            'hedge_costs': total_hedge_costs,
            'net_hedge_pnl': total_hedge_pnl - total_hedge_costs,
            'unrealized_pnl': unrealized_pnl,
            'realized_pnl': realized_pnl,
            'total_pnl': total_pnl,
            'roi': roi,
            'net_hedge_shares': net_hedge_shares,
            'greeks': greeks
        }

    def get_portfolio_pnl(self):
        """
        Calculate portfolio-level P&L.

        Returns:
        --------
        dict
            Portfolio P&L summary
        """
        open_positions = Position.query.filter_by(status='open').all()
        closed_positions = Position.query.filter(Position.status.in_(['closed', 'expired'])).all()

        # Calculate open positions P&L
        open_pnl = 0
        open_option_pnl = 0
        open_hedge_pnl = 0
        open_positions_list = []

        for pos in open_positions:
            try:
                pnl = self.calculate_position_pnl(pos.id)
                open_pnl += pnl['total_pnl']
                open_option_pnl += pnl['option_pnl']
                open_hedge_pnl += pnl['net_hedge_pnl']
                open_positions_list.append(pnl)
            except Exception as e:
                print(f"Error calculating P&L for position {pos.id}: {e}")

        # Calculate closed positions P&L
        closed_pnl = 0
        closed_positions_list = []

        for pos in closed_positions:
            try:
                pnl = self.calculate_position_pnl(pos.id)
                closed_pnl += pnl['total_pnl']
                closed_positions_list.append(pnl)
            except Exception as e:
                print(f"Error calculating P&L for closed position {pos.id}: {e}")

        total_pnl = open_pnl + closed_pnl

        return {
            'total_pnl': total_pnl,
            'open_pnl': open_pnl,
            'closed_pnl': closed_pnl,
            'open_option_pnl': open_option_pnl,
            'open_hedge_pnl': open_hedge_pnl,
            'open_positions_count': len(open_positions),
            'closed_positions_count': len(closed_positions),
            'open_positions': open_positions_list,
            'closed_positions': closed_positions_list[:10]  # Limit to recent 10
        }

    def get_pnl_history(self, position_id=None, days=30):
        """
        Get historical P&L snapshots.

        Parameters:
        -----------
        position_id : int, optional
            Specific position (if None, portfolio level)
        days : int
            Number of days of history

        Returns:
        --------
        list
            Historical P&L data
        """
        since_date = datetime.now() - timedelta(days=days)

        if position_id:
            snapshots = PnLSnapshot.query.filter(
                PnLSnapshot.position_id == position_id,
                PnLSnapshot.snapshot_date >= since_date
            ).order_by(PnLSnapshot.snapshot_date).all()

            return [s.to_dict() for s in snapshots]
        else:
            # Aggregate portfolio snapshots by date
            snapshots = PnLSnapshot.query.filter(
                PnLSnapshot.snapshot_date >= since_date
            ).order_by(PnLSnapshot.snapshot_date).all()

            # Group by date and sum P&L
            df = pd.DataFrame([s.to_dict() for s in snapshots])

            if df.empty:
                return []

            df['date'] = pd.to_datetime(df['snapshot_date']).dt.date

            portfolio_history = df.groupby('date').agg({
                'total_pnl': 'sum',
                'unrealized_pnl': 'sum',
                'realized_pnl': 'sum',
                'delta': 'sum',
                'gamma': 'sum',
                'vega': 'sum',
                'theta': 'sum'
            }).reset_index()

            return portfolio_history.to_dict('records')

    def calculate_seller_pnl(self, position_id):
        """
        Calculate P&L specifically for option sellers.

        For sellers, P&L = Premium Collected - Option Payoff + Hedge P&L - Costs

        Parameters:
        -----------
        position_id : int
            Position ID

        Returns:
        --------
        dict
            Seller-specific P&L metrics
        """
        position = Position.query.get(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        if position.quantity >= 0:
            return {'error': 'Not a short (seller) position'}

        pnl = self.calculate_position_pnl(position_id)

        premium_collected = abs(position.premium_collected) * abs(position.quantity) * self.multiplier
        current_obligation = pnl['current_option_price'] * abs(position.quantity) * self.multiplier

        return {
            'position_id': position_id,
            'symbol': position.symbol,
            'premium_collected': premium_collected,
            'current_obligation': current_obligation,
            'option_profit': premium_collected - current_obligation,
            'hedge_pnl': pnl['net_hedge_pnl'],
            'total_pnl': pnl['total_pnl'],
            'roi': pnl['roi'],
            'max_profit': premium_collected,
            'max_profit_pct': 100,  # Can keep 100% of premium if worthless
            'break_even': position.strike + abs(position.premium_collected) if position.option_type == 'call' else position.strike - abs(position.premium_collected),
            'days_held': pnl['days_held'],
            'annualized_return': (pnl['roi'] * 365 / pnl['days_held']) if pnl['days_held'] > 0 else 0
        }

    def calculate_buyer_pnl(self, position_id):
        """
        Calculate P&L specifically for option buyers.

        For buyers, P&L = Option Payoff - Premium Paid

        Parameters:
        -----------
        position_id : int
            Position ID

        Returns:
        --------
        dict
            Buyer-specific P&L metrics
        """
        position = Position.query.get(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        if position.quantity <= 0:
            return {'error': 'Not a long (buyer) position'}

        pnl = self.calculate_position_pnl(position_id)

        premium_paid = abs(position.premium_collected) * position.quantity * self.multiplier
        current_value = pnl['current_option_price'] * position.quantity * self.multiplier

        # Calculate intrinsic and time value
        intrinsic_value = max(0,
            (pnl['current_underlying_price'] - position.strike) if position.option_type == 'call'
            else (position.strike - pnl['current_underlying_price'])
        ) * position.quantity * self.multiplier

        time_value = current_value - intrinsic_value

        return {
            'position_id': position_id,
            'symbol': position.symbol,
            'premium_paid': premium_paid,
            'current_value': current_value,
            'intrinsic_value': intrinsic_value,
            'time_value': time_value,
            'profit_loss': pnl['total_pnl'],
            'roi': pnl['roi'],
            'max_loss': -premium_paid,
            'max_loss_pct': -100,
            'break_even': position.strike + abs(position.premium_collected) if position.option_type == 'call' else position.strike - abs(position.premium_collected),
            'days_held': pnl['days_held']
        }

    def get_performance_metrics(self, start_date=None, end_date=None):
        """
        Calculate performance metrics for the portfolio.

        Parameters:
        -----------
        start_date : datetime, optional
            Start date for analysis
        end_date : datetime, optional
            End date for analysis

        Returns:
        --------
        dict
            Performance metrics
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now()

        # Get all positions in date range
        positions = Position.query.filter(
            Position.entry_date >= start_date,
            Position.entry_date <= end_date
        ).all()

        total_trades = len(positions)
        winning_trades = 0
        losing_trades = 0
        total_profit = 0
        total_loss = 0
        total_premium_collected = 0
        total_premium_paid = 0

        for pos in positions:
            try:
                pnl = self.calculate_position_pnl(pos.id)

                if pnl['total_pnl'] > 0:
                    winning_trades += 1
                    total_profit += pnl['total_pnl']
                else:
                    losing_trades += 1
                    total_loss += abs(pnl['total_pnl'])

                if pos.quantity < 0:  # Seller
                    total_premium_collected += abs(pos.premium_collected) * abs(pos.quantity) * self.multiplier
                else:  # Buyer
                    total_premium_paid += abs(pos.premium_collected) * pos.quantity * self.multiplier

            except Exception as e:
                print(f"Error in performance calculation for position {pos.id}: {e}")

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        avg_win = (total_profit / winning_trades) if winning_trades > 0 else 0
        avg_loss = (total_loss / losing_trades) if losing_trades > 0 else 0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else float('inf')

        return {
            'period_start': start_date,
            'period_end': end_date,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'net_pnl': total_profit - total_loss,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'total_premium_collected': total_premium_collected,
            'total_premium_paid': total_premium_paid,
            'sharpe_ratio': self._calculate_sharpe_ratio(positions)
        }

    def _calculate_sharpe_ratio(self, positions, risk_free_rate=0.05):
        """Calculate Sharpe ratio for positions"""
        if not positions:
            return 0

        returns = []
        for pos in positions:
            try:
                pnl = self.calculate_position_pnl(pos.id)
                if pos.quantity < 0:
                    capital = abs(pos.premium_collected) * abs(pos.quantity) * self.multiplier
                else:
                    capital = abs(pos.premium_collected) * pos.quantity * self.multiplier

                if capital > 0 and pnl['days_held'] > 0:
                    daily_return = (pnl['total_pnl'] / capital) / pnl['days_held']
                    returns.append(daily_return)
            except:
                continue

        if not returns:
            return 0

        returns_series = pd.Series(returns)
        excess_return = returns_series.mean() - (risk_free_rate / 252)
        return_std = returns_series.std()

        if return_std > 0:
            sharpe = (excess_return / return_std) * (252 ** 0.5)  # Annualized
            return sharpe
        else:
            return 0

    def get_pnl_attribution(self, position_id):
        """
        Break down P&L by source (option, hedge, time decay, etc.)

        Parameters:
        -----------
        position_id : int
            Position ID

        Returns:
        --------
        dict
            P&L attribution
        """
        pnl = self.calculate_position_pnl(position_id)

        # Estimate time decay contribution (theta)
        theta_contribution = pnl['greeks']['theta'] * pnl['days_held']

        # Delta contribution (from underlying movement)
        delta_contribution = pnl['greeks']['delta'] * pnl['underlying_change'] * abs(pnl['quantity']) * self.multiplier

        return {
            'position_id': position_id,
            'total_pnl': pnl['total_pnl'],
            'attribution': {
                'option_pnl': pnl['option_pnl'],
                'hedge_pnl': pnl['net_hedge_pnl'],
                'estimated_theta_pnl': theta_contribution,
                'estimated_delta_pnl': delta_contribution,
                'transaction_costs': pnl['hedge_costs']
            }
        }
