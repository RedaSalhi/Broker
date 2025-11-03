"""
Portfolio Management

Manages portfolio of options positions, calculates portfolio-level Greeks,
and enforces risk limits.
"""
from datetime import datetime, date
from models.greeks import calculate_all_greeks
from models.black_scholes import black_scholes_price
from data.database import db, Position, Hedge, PnLSnapshot, RiskLimit


class Portfolio:
    """Portfolio manager for options positions"""

    def __init__(self, market_data_manager):
        self.market_data = market_data_manager
        self.multiplier = 100  # Standard options multiplier

    def add_position(self, symbol, option_type, strike, expiration, quantity,
                    premium, implied_vol=None, dividend_yield=0):
        """
        Add a new position to the portfolio.

        Parameters:
        -----------
        symbol : str
            Underlying ticker
        option_type : str
            'call' or 'put'
        strike : float
            Strike price
        expiration : date
            Expiration date
        quantity : int
            Number of contracts (negative for short)
        premium : float
            Premium per contract
        implied_vol : float
            Implied volatility (if None, will use historical vol)
        dividend_yield : float
            Dividend yield

        Returns:
        --------
        Position
            Created position object
        """
        # Get current market data
        market_data = self.market_data.get_stock_price(symbol)
        current_price = market_data['price']

        # Get volatility if not provided
        if implied_vol is None:
            implied_vol = self.market_data.get_historical_volatility(symbol)

        # Get risk-free rate
        risk_free_rate = self.market_data.get_risk_free_rate()

        # Create position
        position = Position(
            symbol=symbol,
            option_type=option_type,
            strike=strike,
            expiration=expiration,
            quantity=quantity,
            premium_collected=premium if quantity < 0 else -premium,
            entry_price=current_price,
            implied_vol=implied_vol,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
            status='open'
        )

        # Check risk limits before adding
        if not self._check_risk_limits(position):
            raise ValueError("Position would breach risk limits")

        db.session.add(position)
        db.session.commit()

        # Create initial P&L snapshot
        self.update_position_pnl(position)

        return position

    def close_position(self, position_id, close_price=None):
        """
        Close an existing position.

        Parameters:
        -----------
        position_id : int
            Position ID to close
        close_price : float
            Option price at close (if None, will calculate)

        Returns:
        --------
        dict
            Final P&L summary
        """
        position = Position.query.get(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        if position.status != 'open':
            raise ValueError(f"Position {position_id} is not open")

        # Calculate current option price if not provided
        if close_price is None:
            days_to_expiry = (position.expiration - date.today()).days
            T = max(days_to_expiry / 365.0, 0)

            market_data = self.market_data.get_stock_price(position.symbol)
            current_price = market_data['price']

            close_price = black_scholes_price(
                S=current_price,
                K=position.strike,
                T=T,
                r=position.risk_free_rate,
                sigma=position.implied_vol,
                option_type=position.option_type,
                q=position.dividend_yield
            )

        # Update position
        position.status = 'closed'
        position.close_date = datetime.utcnow()
        position.close_price = close_price

        # Calculate final P&L
        final_pnl = self._calculate_position_pnl(position, close_price)

        db.session.commit()

        return final_pnl

    def get_portfolio_greeks(self):
        """
        Calculate portfolio-level Greeks.

        Returns:
        --------
        dict
            Aggregated Greeks for all open positions
        """
        open_positions = Position.query.filter_by(status='open').all()

        portfolio_greeks = {
            'delta': 0,
            'gamma': 0,
            'vega': 0,
            'theta': 0,
            'rho': 0
        }

        position_details = []

        for position in open_positions:
            try:
                # Get current market data
                market_data = self.market_data.get_stock_price(position.symbol)
                current_price = market_data['price']

                # Calculate time to expiration
                days_to_expiry = (position.expiration - date.today()).days
                T = max(days_to_expiry / 365.0, 0.0001)  # Avoid zero

                # Calculate Greeks
                greeks = calculate_all_greeks(
                    S=current_price,
                    K=position.strike,
                    T=T,
                    r=position.risk_free_rate,
                    sigma=position.implied_vol,
                    option_type=position.option_type,
                    q=position.dividend_yield
                )

                # Scale by position size
                position_size = position.quantity * self.multiplier

                position_greeks = {
                    'position_id': position.id,
                    'symbol': position.symbol,
                    'delta': greeks['delta'] * position_size,
                    'gamma': greeks['gamma'] * position_size,
                    'vega': greeks['vega'] * position_size,
                    'theta': greeks['theta'] * position_size,
                    'rho': greeks['rho'] * position_size
                }

                position_details.append(position_greeks)

                # Aggregate to portfolio level
                for greek in portfolio_greeks:
                    portfolio_greeks[greek] += position_greeks[greek]

            except Exception as e:
                print(f"Error calculating Greeks for position {position.id}: {e}")
                continue

        return {
            'portfolio': portfolio_greeks,
            'positions': position_details
        }

    def update_position_pnl(self, position):
        """
        Update P&L snapshot for a position.

        Parameters:
        -----------
        position : Position
            Position object to update
        """
        try:
            # Get current market data
            market_data = self.market_data.get_stock_price(position.symbol)
            current_price = market_data['price']

            # Calculate time to expiration
            days_to_expiry = (position.expiration - date.today()).days
            T = max(days_to_expiry / 365.0, 0)

            # Calculate current option price
            option_price = black_scholes_price(
                S=current_price,
                K=position.strike,
                T=T,
                r=position.risk_free_rate,
                sigma=position.implied_vol,
                option_type=position.option_type,
                q=position.dividend_yield
            )

            # Calculate Greeks
            greeks = calculate_all_greeks(
                S=current_price,
                K=position.strike,
                T=T,
                r=position.risk_free_rate,
                sigma=position.implied_vol,
                option_type=position.option_type,
                q=position.dividend_yield
            )

            # Calculate P&L
            pnl = self._calculate_position_pnl(position, option_price)

            # Create snapshot
            snapshot = PnLSnapshot(
                position_id=position.id,
                underlying_price=current_price,
                option_price=option_price,
                delta=greeks['delta'],
                gamma=greeks['gamma'],
                vega=greeks['vega'],
                theta=greeks['theta'],
                unrealized_pnl=pnl['unrealized_pnl'],
                realized_pnl=pnl['realized_pnl'],
                total_pnl=pnl['total_pnl']
            )

            db.session.add(snapshot)
            db.session.commit()

        except Exception as e:
            print(f"Error updating P&L for position {position.id}: {e}")

    def _calculate_position_pnl(self, position, current_option_price):
        """
        Calculate P&L for a position.

        Returns:
        --------
        dict
            P&L breakdown
        """
        # Option P&L
        if position.quantity < 0:  # Short position
            # Sold at premium_collected, mark-to-market at current price
            option_pnl = (position.premium_collected + current_option_price) * abs(position.quantity) * self.multiplier
        else:  # Long position
            option_pnl = (current_option_price - abs(position.premium_collected)) * position.quantity * self.multiplier

        # Hedge P&L
        hedge_pnl = 0
        hedge_costs = 0

        for hedge in position.hedges:
            hedge_costs += hedge.transaction_cost

        # Get current underlying price
        try:
            market_data = self.market_data.get_stock_price(position.symbol)
            current_underlying = market_data['price']

            # Calculate hedge P&L (cumulative)
            for hedge in position.hedges:
                hedge_pnl += hedge.hedge_quantity * (current_underlying - hedge.hedge_price)

        except:
            pass

        unrealized_pnl = option_pnl + hedge_pnl
        realized_pnl = -hedge_costs  # Costs are realized

        return {
            'option_pnl': option_pnl,
            'hedge_pnl': hedge_pnl,
            'hedge_costs': hedge_costs,
            'unrealized_pnl': unrealized_pnl,
            'realized_pnl': realized_pnl,
            'total_pnl': unrealized_pnl + realized_pnl
        }

    def get_positions_summary(self):
        """
        Get summary of all positions.

        Returns:
        --------
        dict
            Portfolio summary
        """
        open_positions = Position.query.filter_by(status='open').all()
        closed_positions = Position.query.filter_by(status='closed').count()

        total_value = 0
        total_pnl = 0

        positions_list = []

        for pos in open_positions:
            try:
                # Get current price
                market_data = self.market_data.get_stock_price(pos.symbol)
                current_price = market_data['price']

                # Calculate time to expiration
                days_to_expiry = (pos.expiration - date.today()).days
                T = max(days_to_expiry / 365.0, 0)

                # Calculate current option price
                option_price = black_scholes_price(
                    S=current_price,
                    K=pos.strike,
                    T=T,
                    r=pos.risk_free_rate,
                    sigma=pos.implied_vol,
                    option_type=pos.option_type,
                    q=pos.dividend_yield
                )

                # Calculate P&L
                pnl = self._calculate_position_pnl(pos, option_price)

                position_value = option_price * abs(pos.quantity) * self.multiplier

                total_value += position_value
                total_pnl += pnl['total_pnl']

                positions_list.append({
                    'id': pos.id,
                    'symbol': pos.symbol,
                    'type': pos.option_type,
                    'strike': pos.strike,
                    'expiration': pos.expiration,
                    'quantity': pos.quantity,
                    'current_price': current_price,
                    'option_price': option_price,
                    'value': position_value,
                    'pnl': pnl['total_pnl'],
                    'days_to_expiry': days_to_expiry
                })

            except Exception as e:
                print(f"Error processing position {pos.id}: {e}")
                continue

        return {
            'open_positions': len(open_positions),
            'closed_positions': closed_positions,
            'total_value': total_value,
            'total_pnl': total_pnl,
            'positions': positions_list
        }

    def _check_risk_limits(self, new_position):
        """
        Check if adding a position would breach risk limits.

        Parameters:
        -----------
        new_position : Position
            Position to check

        Returns:
        --------
        bool
            True if within limits, False otherwise
        """
        # For now, return True - full implementation would check against RiskLimit table
        return True

    def expire_positions(self):
        """
        Mark expired positions and calculate final P&L.
        """
        today = date.today()
        expired = Position.query.filter(
            Position.expiration < today,
            Position.status == 'open'
        ).all()

        for position in expired:
            # Calculate intrinsic value at expiration
            market_data = self.market_data.get_stock_price(position.symbol)
            final_price = market_data['price']

            if position.option_type == 'call':
                intrinsic = max(0, final_price - position.strike)
            else:  # put
                intrinsic = max(0, position.strike - final_price)

            position.status = 'expired'
            position.close_date = datetime.utcnow()
            position.close_price = intrinsic

            # Final P&L snapshot
            pnl = self._calculate_position_pnl(position, intrinsic)

            snapshot = PnLSnapshot(
                position_id=position.id,
                underlying_price=final_price,
                option_price=intrinsic,
                unrealized_pnl=pnl['unrealized_pnl'],
                realized_pnl=pnl['realized_pnl'],
                total_pnl=pnl['total_pnl']
            )

            db.session.add(snapshot)

        db.session.commit()

        return len(expired)
