"""
Kelly Criterion position sizing for the trading system.

Kelly formula: f* = (bp - q) / b
  b = win/loss ratio (avg_winner / avg_loser)
  p = win probability
  q = 1 - p

Always uses 0.25x (quarter Kelly) for safety.
Hard cap: never risk more than 2% per trade.
Conservative default: 1.5% risk when < 20 historical trades.
"""

from typing import Optional

FRACTIONAL_KELLY = 0.25
MAX_RISK_FRACTION = 0.02       # 2% hard cap
DEFAULT_RISK_FRACTION = 0.015  # 1.5% conservative default
MIN_TRADES_FOR_KELLY = 20


def calculate_kelly_fraction(
    win_rate: float,
    avg_winner_pct: float,
    avg_loser_pct: float,
) -> float:
    """
    Calculate the fractional Kelly position size as a fraction of capital.

    Args:
        win_rate:       Probability of a winning trade (0.0 – 1.0).
        avg_winner_pct: Average percentage gain on winning trades (positive, e.g. 3.5 for 3.5%).
        avg_loser_pct:  Average percentage loss on losing trades (positive magnitude, e.g. 1.8 for 1.8%).

    Returns:
        Fraction of capital to risk (e.g. 0.015 means 1.5%).
        Returns 0.0 if the strategy has a negative edge.
    """
    try:
        win_rate = float(win_rate)
        avg_winner_pct = float(avg_winner_pct)
        avg_loser_pct = float(avg_loser_pct)

        if not (0.0 < win_rate < 1.0):
            return 0.0
        if avg_winner_pct <= 0.0 or avg_loser_pct <= 0.0:
            return 0.0

        p = win_rate
        q = 1.0 - win_rate
        b = avg_winner_pct / avg_loser_pct  # win/loss ratio

        full_kelly = (b * p - q) / b

        if full_kelly <= 0.0:
            return 0.0

        fractional = full_kelly * FRACTIONAL_KELLY

        # Apply hard cap
        fractional = min(fractional, MAX_RISK_FRACTION)

        return round(fractional, 6)

    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def get_position_size(
    account_balance: float,
    kelly_fraction: float,
    entry_price: float,
    stop_loss: float,
) -> float:
    """
    Calculate the £ amount to invest based on Kelly fraction and the
    entry/stop-loss gap.

    The Kelly fraction represents the proportion of capital to *risk*.
    The actual position size is scaled so that if the stop-loss is hit the
    loss equals exactly kelly_fraction * account_balance.

    Args:
        account_balance: Current account balance in £.
        kelly_fraction:  Fraction of capital to risk per trade (e.g. 0.015).
        entry_price:     Entry price per share.
        stop_loss:       Stop-loss price per share.

    Returns:
        Position size in £ (amount to invest). Returns 0.0 on invalid inputs.
    """
    try:
        account_balance = float(account_balance)
        kelly_fraction = float(kelly_fraction)
        entry_price = float(entry_price)
        stop_loss = float(stop_loss)

        if account_balance <= 0.0:
            return 0.0
        if entry_price <= 0.0:
            return 0.0
        if kelly_fraction <= 0.0:
            return 0.0
        if stop_loss <= 0.0 or stop_loss >= entry_price:
            return 0.0

        risk_per_trade_gbp = account_balance * kelly_fraction

        # Distance from entry to stop as a fraction of entry price
        risk_pct_per_share = (entry_price - stop_loss) / entry_price

        if risk_pct_per_share <= 0.0:
            return 0.0

        # Scale position so that hitting stop = risk_per_trade_gbp loss
        position_size = risk_per_trade_gbp / risk_pct_per_share

        # Never invest more than the account balance
        position_size = min(position_size, account_balance)

        return round(position_size, 2)

    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def kelly_from_historical_trades(closed_positions: list) -> dict:
    """
    Analyse closed positions and derive Kelly sizing parameters.

    Args:
        closed_positions: List of closed position dicts from portfolio.get_closed_positions().
                          Each dict must contain 'pnl_pct' (float, signed).

    Returns:
        {
            'win_rate':                float,   # 0.0 – 1.0
            'avg_winner_pct':          float,   # positive magnitude
            'avg_loser_pct':           float,   # positive magnitude
            'kelly_fraction':          float,   # fraction of capital to risk
            'recommended_risk_per_trade': float, # same as kelly_fraction (convenience alias)
            'trade_count':             int,
            'insufficient_data':       bool,
        }
    """
    result = {
        "win_rate": 0.0,
        "avg_winner_pct": 0.0,
        "avg_loser_pct": 0.0,
        "kelly_fraction": DEFAULT_RISK_FRACTION,
        "recommended_risk_per_trade": DEFAULT_RISK_FRACTION,
        "trade_count": 0,
        "insufficient_data": True,
    }

    try:
        if not closed_positions or not isinstance(closed_positions, list):
            return result

        pnl_pcts = []
        for pos in closed_positions:
            try:
                pnl_pct = float(pos.get("pnl_pct", 0.0))
                pnl_pcts.append(pnl_pct)
            except (TypeError, ValueError):
                continue

        trade_count = len(pnl_pcts)
        result["trade_count"] = trade_count

        if trade_count < MIN_TRADES_FOR_KELLY:
            result["insufficient_data"] = True
            result["kelly_fraction"] = DEFAULT_RISK_FRACTION
            result["recommended_risk_per_trade"] = DEFAULT_RISK_FRACTION
            return result

        winners = [p for p in pnl_pcts if p > 0.0]
        losers = [p for p in pnl_pcts if p <= 0.0]

        win_rate = len(winners) / trade_count if trade_count > 0 else 0.0
        avg_winner_pct = sum(winners) / len(winners) if winners else 0.0
        avg_loser_pct = abs(sum(losers) / len(losers)) if losers else 0.0

        result["win_rate"] = round(win_rate, 4)
        result["avg_winner_pct"] = round(avg_winner_pct, 4)
        result["avg_loser_pct"] = round(avg_loser_pct, 4)
        result["insufficient_data"] = False

        if avg_loser_pct == 0.0 or win_rate == 0.0:
            kelly = 0.0
        else:
            kelly = calculate_kelly_fraction(win_rate, avg_winner_pct, avg_loser_pct)

        if kelly <= 0.0:
            # Losing or break-even strategy — return 0 to signal no trade
            result["kelly_fraction"] = 0.0
            result["recommended_risk_per_trade"] = 0.0
        else:
            result["kelly_fraction"] = kelly
            result["recommended_risk_per_trade"] = kelly

        return result

    except Exception:
        return result
