"""
Risk Management and Alerts

Monitors portfolio risk metrics and sends alerts when limits are breached.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from data.database import db, Position, RiskLimit
from models.portfolio import Portfolio
from utils.hedging import DeltaHedger
import config


class RiskManager:
    """Risk management and monitoring"""

    def __init__(self, market_data_manager):
        self.market_data = market_data_manager
        self.portfolio = Portfolio(market_data_manager)
        self.hedger = DeltaHedger(market_data_manager)

    def check_risk_limits(self):
        """
        Check all risk limits and return breaches.

        Returns:
        --------
        dict
            Risk limit status and breaches
        """
        breaches = []

        # Check delta exposure
        delta_exposure = self.hedger.get_portfolio_delta_exposure()
        total_delta = abs(delta_exposure['total_portfolio_delta'])

        delta_limit = RiskLimit.query.filter_by(limit_type='max_delta_exposure').first()
        if delta_limit and total_delta > delta_limit.limit_value:
            breaches.append({
                'type': 'max_delta_exposure',
                'current': total_delta,
                'limit': delta_limit.limit_value,
                'severity': 'high',
                'message': f"Portfolio delta {total_delta:.0f} exceeds limit {delta_limit.limit_value:.0f}"
            })

        # Check portfolio Greeks
        greeks_data = self.portfolio.get_portfolio_greeks()
        portfolio_greeks = greeks_data['portfolio']

        vega_limit = RiskLimit.query.filter_by(limit_type='max_vega_exposure').first()
        if vega_limit and abs(portfolio_greeks['vega']) > vega_limit.limit_value:
            breaches.append({
                'type': 'max_vega_exposure',
                'current': abs(portfolio_greeks['vega']),
                'limit': vega_limit.limit_value,
                'severity': 'medium',
                'message': f"Portfolio vega {abs(portfolio_greeks['vega']):.0f} exceeds limit {vega_limit.limit_value:.0f}"
            })

        # Check position sizes
        position_limit = RiskLimit.query.filter_by(limit_type='max_position_size').first()
        if position_limit:
            large_positions = Position.query.filter(
                Position.status == 'open',
                db.func.abs(Position.quantity) > position_limit.limit_value
            ).all()

            for pos in large_positions:
                breaches.append({
                    'type': 'max_position_size',
                    'current': abs(pos.quantity),
                    'limit': position_limit.limit_value,
                    'severity': 'medium',
                    'message': f"Position {pos.symbol} size {abs(pos.quantity)} exceeds limit {position_limit.limit_value}",
                    'position_id': pos.id
                })

        # Check concentration
        concentration_limit = RiskLimit.query.filter_by(limit_type='max_concentration').first()
        if concentration_limit:
            positions_summary = self.portfolio.get_positions_summary()
            total_value = positions_summary['total_value']

            if total_value > 0:
                # Group by symbol
                symbol_exposure = {}
                for pos_data in positions_summary['positions']:
                    symbol = pos_data['symbol']
                    value = abs(pos_data['value'])
                    symbol_exposure[symbol] = symbol_exposure.get(symbol, 0) + value

                for symbol, exposure in symbol_exposure.items():
                    concentration = exposure / total_value
                    if concentration > concentration_limit.limit_value:
                        breaches.append({
                            'type': 'max_concentration',
                            'symbol': symbol,
                            'current': concentration,
                            'limit': concentration_limit.limit_value,
                            'severity': 'medium',
                            'message': f"Concentration in {symbol} ({concentration*100:.1f}%) exceeds limit ({concentration_limit.limit_value*100:.1f}%)"
                        })

        # Update breach counts
        for breach in breaches:
            limit = RiskLimit.query.filter_by(limit_type=breach['type']).first()
            if limit:
                limit.breach_count += 1
                limit.last_updated = datetime.utcnow()

        db.session.commit()

        return {
            'has_breaches': len(breaches) > 0,
            'breach_count': len(breaches),
            'breaches': breaches,
            'timestamp': datetime.utcnow()
        }

    def get_risk_report(self):
        """
        Generate comprehensive risk report.

        Returns:
        --------
        dict
            Risk metrics and status
        """
        # Portfolio Greeks
        greeks_data = self.portfolio.get_portfolio_greeks()
        portfolio_greeks = greeks_data['portfolio']

        # Delta exposure
        delta_exposure = self.hedger.get_portfolio_delta_exposure()

        # Positions summary
        positions_summary = self.portfolio.get_positions_summary()

        # Get all risk limits
        limits = RiskLimit.query.all()
        limits_status = {}

        for limit in limits:
            if limit.limit_type == 'max_delta_exposure':
                current = abs(delta_exposure['total_portfolio_delta'])
            elif limit.limit_type == 'max_vega_exposure':
                current = abs(portfolio_greeks['vega'])
            elif limit.limit_type == 'max_position_size':
                max_position = db.session.query(
                    db.func.max(db.func.abs(Position.quantity))
                ).filter_by(status='open').scalar() or 0
                current = max_position
            elif limit.limit_type == 'max_concentration':
                # Calculate max concentration
                total_value = positions_summary['total_value']
                if total_value > 0:
                    symbol_exposure = {}
                    for pos_data in positions_summary['positions']:
                        symbol = pos_data['symbol']
                        value = abs(pos_data['value'])
                        symbol_exposure[symbol] = symbol_exposure.get(symbol, 0) + value
                    current = max(symbol_exposure.values()) / total_value if symbol_exposure else 0
                else:
                    current = 0
            else:
                current = 0

            limits_status[limit.limit_type] = {
                'current': current,
                'limit': limit.limit_value,
                'utilization': (current / limit.limit_value * 100) if limit.limit_value > 0 else 0,
                'breach_count': limit.breach_count,
                'status': 'OK' if current <= limit.limit_value else 'BREACH'
            }

        return {
            'portfolio_greeks': portfolio_greeks,
            'delta_exposure': delta_exposure,
            'positions_summary': {
                'open_positions': positions_summary['open_positions'],
                'total_value': positions_summary['total_value'],
                'total_pnl': positions_summary['total_pnl']
            },
            'risk_limits': limits_status,
            'timestamp': datetime.utcnow()
        }

    def send_alert(self, subject, message, severity='info'):
        """
        Send email alert.

        Parameters:
        -----------
        subject : str
            Email subject
        message : str
            Email body
        severity : str
            Alert severity: info, warning, critical
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = config.EMAIL_RECIPIENT
            msg['To'] = config.EMAIL_RECIPIENT
            msg['Subject'] = f"[{severity.upper()}] {subject}"

            # Email body
            body = f"""
Options Trading Platform Alert

Severity: {severity.upper()}
Timestamp: {datetime.utcnow()}

{message}

---
This is an automated alert from your Options Trading Platform.
            """

            msg.attach(MIMEText(body, 'plain'))

            # Note: This is a placeholder. You would need to configure SMTP settings
            # For production, use a service like SendGrid, AWS SES, or configure SMTP
            print(f"\n[ALERT] {severity.upper()}: {subject}")
            print(f"Message: {message}\n")

            # Uncomment and configure for actual email sending:
            # server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
            # server.starttls()
            # server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            # server.send_message(msg)
            # server.quit()

        except Exception as e:
            print(f"Error sending alert: {e}")

    def monitor_and_alert(self):
        """
        Monitor risk limits and send alerts for breaches.

        Returns:
        --------
        dict
            Monitoring results
        """
        risk_status = self.check_risk_limits()

        if risk_status['has_breaches']:
            # Send alert for high severity breaches
            high_severity = [b for b in risk_status['breaches'] if b['severity'] == 'high']

            if high_severity:
                message = "High severity risk limit breaches detected:\n\n"
                for breach in high_severity:
                    message += f"- {breach['message']}\n"

                self.send_alert(
                    subject="High Severity Risk Limit Breach",
                    message=message,
                    severity='critical'
                )

            # Log all breaches
            for breach in risk_status['breaches']:
                print(f"[RISK BREACH] {breach['severity'].upper()}: {breach['message']}")

        return risk_status

    def check_expiring_positions(self, days_threshold=7):
        """
        Check for positions expiring soon.

        Parameters:
        -----------
        days_threshold : int
            Alert if expiring within this many days

        Returns:
        --------
        list
            Expiring positions
        """
        from datetime import date, timedelta

        expiration_date = date.today() + timedelta(days=days_threshold)

        expiring = Position.query.filter(
            Position.status == 'open',
            Position.expiration <= expiration_date
        ).all()

        if expiring:
            message = f"You have {len(expiring)} position(s) expiring within {days_threshold} days:\n\n"
            for pos in expiring:
                days_left = (pos.expiration - date.today()).days
                message += f"- {pos.symbol} {pos.option_type.upper()} ${pos.strike} expires in {days_left} day(s)\n"

            self.send_alert(
                subject=f"Positions Expiring Soon ({len(expiring)})",
                message=message,
                severity='warning'
            )

        return [p.to_dict() for p in expiring]

    def stress_test(self, underlying_change_pct):
        """
        Run stress test on portfolio.

        Parameters:
        -----------
        underlying_change_pct : float
            Percentage change in underlying prices

        Returns:
        --------
        dict
            Stress test results
        """
        from models.black_scholes import black_scholes_price
        from datetime import date

        open_positions = Position.query.filter_by(status='open').all()

        total_pnl_impact = 0
        position_impacts = []

        for pos in open_positions:
            try:
                # Get current price
                market_data = self.market_data.get_stock_price(pos.symbol)
                current_price = market_data['price']

                # Calculate stressed price
                stressed_price = current_price * (1 + underlying_change_pct / 100)

                # Calculate time to expiration
                days_to_expiry = (pos.expiration - date.today()).days
                T = max(days_to_expiry / 365.0, 0)

                # Calculate stressed option price
                stressed_option_price = black_scholes_price(
                    S=stressed_price,
                    K=pos.strike,
                    T=T,
                    r=pos.risk_free_rate,
                    sigma=pos.implied_vol,
                    option_type=pos.option_type,
                    q=pos.dividend_yield
                )

                # Calculate current option price
                current_option_price = black_scholes_price(
                    S=current_price,
                    K=pos.strike,
                    T=T,
                    r=pos.risk_free_rate,
                    sigma=pos.implied_vol,
                    option_type=pos.option_type,
                    q=pos.dividend_yield
                )

                # Calculate P&L impact
                if pos.quantity < 0:  # Short
                    pnl_impact = (current_option_price - stressed_option_price) * abs(pos.quantity) * 100
                else:  # Long
                    pnl_impact = (stressed_option_price - current_option_price) * pos.quantity * 100

                total_pnl_impact += pnl_impact

                position_impacts.append({
                    'position_id': pos.id,
                    'symbol': pos.symbol,
                    'pnl_impact': pnl_impact,
                    'current_price': current_price,
                    'stressed_price': stressed_price
                })

            except Exception as e:
                print(f"Error in stress test for position {pos.id}: {e}")

        return {
            'scenario': f"{underlying_change_pct:+.1f}% underlying move",
            'total_pnl_impact': total_pnl_impact,
            'position_impacts': position_impacts,
            'timestamp': datetime.utcnow()
        }
