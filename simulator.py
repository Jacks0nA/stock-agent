"""
Portfolio simulation engine based on backtest_results.json
Calculates performance metrics for a £30,000 starting portfolio
"""

import json
import math
from datetime import datetime, timedelta
from collections import defaultdict
from scipy import stats
import numpy as np

# Constants
STARTING_BALANCE = 30000.0
RISK_FREE_RATE = 0.045  # 4.5% UK base rate
MAX_POSITIONS = 5
STOP_LOSS_THRESHOLD = -0.01  # -1%

# Confidence tier position sizes
POSITION_SIZES = {
    "LOW": 100.0,
    "MEDIUM": 250.0,
    "CONFIDENT": 1000.0,
    "SUPER": 2000.0,
}


def infer_confidence_from_rsi(rsi):
    """Map RSI values to confidence tiers"""
    if rsi < 35:
        return "SUPER"  # Oversold, strong bounce setup
    elif rsi < 45:
        return "CONFIDENT"  # Moderately oversold
    elif rsi < 60:
        return "MEDIUM"  # Normal range
    else:
        return "LOW"  # Already recovered, less edge


def parse_date(date_str):
    """Parse date string to datetime"""
    return datetime.strptime(date_str, "%Y-%m-%d")


def get_best_checkpoint(trade):
    """Get the best checkpoint (highest gain) from day 1, 3, or 5"""
    checkpoints = {
        1: trade["change_1d"],
        3: trade["change_3d"],
        5: trade["change_5d"],
    }
    best_day = max(checkpoints, key=checkpoints.get)
    return best_day, checkpoints[best_day]


def get_worst_checkpoint(trade):
    """Get the worst checkpoint (largest loss) from day 1, 3, or 5"""
    checkpoints = {
        1: trade["change_1d"],
        3: trade["change_3d"],
        5: trade["change_5d"],
    }
    worst_day = min(checkpoints, key=checkpoints.get)
    return worst_day, checkpoints[worst_day]


def calculate_sharpe_ratio(returns, risk_free_rate=0.045):
    """Calculate Sharpe ratio from returns array"""
    if len(returns) < 2:
        return 0

    returns_array = np.array(returns)
    excess_returns = returns_array - (risk_free_rate / 252)  # Daily risk-free rate

    if np.std(excess_returns) == 0:
        return 0

    sharpe = np.mean(excess_returns) / np.std(excess_returns)
    # Annualize (252 trading days)
    return sharpe * np.sqrt(252)


def calculate_max_drawdown(portfolio_values):
    """Calculate maximum drawdown from portfolio value series"""
    if not portfolio_values:
        return 0

    peak = portfolio_values[0]
    max_dd = 0

    for value in portfolio_values:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak
        max_dd = max(max_dd, drawdown)

    return max_dd


def load_backtest_results(filepath):
    """Load backtest results from JSON file"""
    with open(filepath, "r") as f:
        return json.load(f)


def simulate_portfolio(signals):
    """Simulate portfolio trading based on signals"""
    portfolio_balance = STARTING_BALANCE
    positions = []  # Active positions: {ticker, entry_price, entry_date, size, confidence, exit_day, exit_price, pnl}
    closed_trades = []
    portfolio_values = [STARTING_BALANCE]
    returns = []
    daily_values = defaultdict(float)

    for signal in signals:
        ticker = signal["ticker"]
        date = signal["date"]
        price = signal["price"]
        rsi = signal.get("rsi", 50)  # Default to neutral RSI if missing

        # Trade on WATCH or NEUTRAL signals (the actual trading opportunities)
        # Skip AVOID signals
        if signal.get("signal") == "AVOID":
            continue

        # Infer confidence from RSI
        confidence = infer_confidence_from_rsi(rsi)
        position_size = POSITION_SIZES[confidence]

        # Check if we have enough capital and haven't hit max positions
        if portfolio_balance >= position_size and len(positions) < MAX_POSITIONS:
            # Check worst checkpoint for stop loss
            worst_day, worst_change = get_worst_checkpoint(signal)
            if worst_change < STOP_LOSS_THRESHOLD:
                # Would hit stop loss, skip this trade
                continue

            # Enter position
            best_day, best_change = get_best_checkpoint(signal)

            # Calculate exit price and P&L
            exit_price = price * (1 + best_change / 100)
            pnl = position_size * (best_change / 100)
            pnl_pct = best_change

            trade = {
                "ticker": ticker,
                "entry_date": date,
                "entry_price": price,
                "size": position_size,
                "confidence": confidence,
                "exit_day": best_day,
                "exit_price": exit_price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "hold_days": best_day,
            }

            # Update portfolio
            portfolio_balance -= position_size
            closed_trades.append(trade)

            # Record for analytics
            if pnl > 0:
                returns.append(pnl / STARTING_BALANCE)
            else:
                returns.append(pnl / STARTING_BALANCE)

            daily_values[date] = portfolio_balance + sum(p["size"] for p in positions)

    # Calculate final portfolio value
    total_pnl = sum(t["pnl"] for t in closed_trades)
    final_balance = portfolio_balance + total_pnl

    return {
        "closed_trades": closed_trades,
        "final_balance": final_balance,
        "total_pnl": total_pnl,
        "returns": returns,
        "starting_balance": STARTING_BALANCE,
    }


def calculate_metrics(results, signals):
    """Calculate all performance metrics"""
    closed_trades = results["closed_trades"]
    final_balance = results["final_balance"]
    total_pnl = results["total_pnl"]
    returns = results["returns"]
    starting_balance = results["starting_balance"]

    # Basic metrics
    total_return_pct = (total_pnl / starting_balance) * 100
    total_return_gbp = total_pnl

    # Win rate
    wins = len([t for t in closed_trades if t["pnl"] > 0])
    total_trades = len(closed_trades)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    # Win rate by confidence tier
    tier_stats = defaultdict(lambda: {"wins": 0, "total": 0})
    for trade in closed_trades:
        tier = trade["confidence"]
        tier_stats[tier]["total"] += 1
        if trade["pnl"] > 0:
            tier_stats[tier]["wins"] += 1

    tier_win_rates = {}
    for tier in ["LOW", "MEDIUM", "CONFIDENT", "SUPER"]:
        stats_data = tier_stats.get(tier, {})
        total = stats_data.get("total", 0)
        wins = stats_data.get("wins", 0)
        tier_win_rates[tier] = (wins / total * 100) if total > 0 else 0

    # Average hold time
    avg_hold_days = (
        np.mean([t["hold_days"] for t in closed_trades])
        if closed_trades
        else 0
    )

    # Sharpe ratio
    sharpe = calculate_sharpe_ratio(returns, RISK_FREE_RATE)

    # Maximum drawdown - simulate portfolio values over time
    portfolio_values = [STARTING_BALANCE]
    current_balance = STARTING_BALANCE
    for trade in closed_trades:
        current_balance += trade["pnl"]
        portfolio_values.append(current_balance)

    max_drawdown_pct = calculate_max_drawdown(portfolio_values) * 100

    # Calmar ratio
    calmar = (
        (total_return_pct / 100) / max_drawdown_pct * 100
        if max_drawdown_pct > 0
        else 0
    )

    # P-value on accuracy (binomial test)
    # Test if win rate is significantly different from 50%
    if total_trades > 0:
        p_value = stats.binomtest(wins, total_trades, 0.5, alternative="two-sided").pvalue
    else:
        p_value = 1.0

    return {
        "total_return_gbp": total_return_gbp,
        "total_return_pct": total_return_pct,
        "sharpe_ratio": sharpe,
        "max_drawdown_pct": max_drawdown_pct,
        "calmar_ratio": calmar,
        "win_rate": win_rate,
        "tier_win_rates": tier_win_rates,
        "avg_hold_days": avg_hold_days,
        "p_value": p_value,
        "total_trades": total_trades,
        "wins": wins,
    }


def split_train_test(signals, train_months=18, test_months=6):
    """Split signals into train and test sets by date"""
    if not signals:
        return [], []

    # Sort signals by date
    sorted_signals = sorted(signals, key=lambda x: x["date"])

    # Find date range
    first_date = parse_date(sorted_signals[0]["date"])
    last_date = parse_date(sorted_signals[-1]["date"])
    total_days = (last_date - first_date).days

    # Calculate split point (18 months of data)
    train_end_date = first_date + timedelta(days=int(total_days * (train_months / (train_months + test_months))))

    train_signals = [s for s in sorted_signals if parse_date(s["date"]) <= train_end_date]
    test_signals = [s for s in sorted_signals if parse_date(s["date"]) > train_end_date]

    return train_signals, test_signals


def print_report(overall_metrics, train_metrics, test_metrics):
    """Print formatted performance report"""
    print("\n" + "=" * 70)
    print("PORTFOLIO SIMULATION REPORT".center(70))
    print("=" * 70)

    print("\n📊 OVERALL PERFORMANCE")
    print("-" * 70)
    print(f"Starting Balance:        £{STARTING_BALANCE:,.2f}")
    print(f"Total Return:            £{overall_metrics['total_return_gbp']:,.2f}")
    print(f"Total Return %:          {overall_metrics['total_return_pct']:.2f}%")
    print(f"Total Trades:            {overall_metrics['total_trades']}")
    print(f"Wins:                    {overall_metrics['wins']}")
    print(f"Win Rate:                {overall_metrics['win_rate']:.1f}%")

    print("\n📈 RISK METRICS")
    print("-" * 70)
    print(f"Sharpe Ratio:            {overall_metrics['sharpe_ratio']:.3f}")
    print(f"Maximum Drawdown:        {overall_metrics['max_drawdown_pct']:.2f}%")
    print(f"Calmar Ratio:            {overall_metrics['calmar_ratio']:.3f}")

    print("\n🎯 WIN RATE BY CONFIDENCE TIER")
    print("-" * 70)
    for tier in ["LOW", "MEDIUM", "CONFIDENT", "SUPER"]:
        win_rate = overall_metrics['tier_win_rates'].get(tier, 0)
        print(f"{tier:12} Confidence:  {win_rate:.1f}%")

    print("\n⏱️  TRADE DURATION")
    print("-" * 70)
    print(f"Average Hold Time:       {overall_metrics['avg_hold_days']:.1f} days")

    print("\n📉 STATISTICAL SIGNIFICANCE")
    print("-" * 70)
    print(f"P-Value (Binomial Test): {overall_metrics['p_value']:.4f}")
    if overall_metrics['p_value'] < 0.05:
        print(f"✓ Win rate is statistically significant (p < 0.05)")
    else:
        print(f"✗ Win rate is NOT statistically significant (p >= 0.05)")

    print("\n🔄 OUT-OF-SAMPLE ANALYSIS (18mo Train / 6mo Test)")
    print("-" * 70)

    print("\nTrain Period (First 18 months):")
    print(f"  Total Trades:          {train_metrics['total_trades']}")
    print(f"  Win Rate:              {train_metrics['win_rate']:.1f}%")
    print(f"  Total Return:          £{train_metrics['total_return_gbp']:,.2f} ({train_metrics['total_return_pct']:.2f}%)")
    print(f"  Sharpe Ratio:          {train_metrics['sharpe_ratio']:.3f}")
    print(f"  Max Drawdown:          {train_metrics['max_drawdown_pct']:.2f}%")

    print("\nTest Period (Last 6 months):")
    print(f"  Total Trades:          {test_metrics['total_trades']}")
    print(f"  Win Rate:              {test_metrics['win_rate']:.1f}%")
    print(f"  Total Return:          £{test_metrics['total_return_gbp']:,.2f} ({test_metrics['total_return_pct']:.2f}%)")
    print(f"  Sharpe Ratio:          {test_metrics['sharpe_ratio']:.3f}")
    print(f"  Max Drawdown:          {test_metrics['max_drawdown_pct']:.2f}%")

    print("\n" + "=" * 70)
    print("END OF REPORT".center(70))
    print("=" * 70 + "\n")


def main():
    """Main simulation runner"""
    # Load data
    print("Loading backtest results...")
    data = load_backtest_results("/Users/jacksonamies/stock-agent/backtest_results.json")
    signals = data.get("sample_results", [])

    print(f"Loaded {len(signals)} signals")

    # Run overall simulation
    print("Running overall simulation...")
    overall_results = simulate_portfolio(signals)
    overall_metrics = calculate_metrics(overall_results, signals)

    # Split into train/test
    print("Splitting into train/test sets...")
    train_signals, test_signals = split_train_test(signals)

    print(f"Train period: {len(train_signals)} signals")
    print(f"Test period: {len(test_signals)} signals")

    # Run train/test simulations
    train_results = simulate_portfolio(train_signals)
    train_metrics = calculate_metrics(train_results, train_signals)

    test_results = simulate_portfolio(test_signals)
    test_metrics = calculate_metrics(test_results, test_signals)

    # Print report
    print_report(overall_metrics, train_metrics, test_metrics)


if __name__ == "__main__":
    main()
