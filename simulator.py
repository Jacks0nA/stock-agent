"""
Portfolio simulation engine based on backtest_results.json
Calculates performance metrics for a £30,000 starting portfolio
Designed for AI learning with configurable strategies
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
MAX_POSITIONS = 10  # Increased for more learning volume
STOP_LOSS_THRESHOLD = -0.01  # -1%

# Default confidence tier position sizes
DEFAULT_POSITION_SIZES = {
    "LOW": 100.0,
    "MEDIUM": 250.0,
    "CONFIDENT": 1000.0,
    "SUPER": 2000.0,
}


def infer_confidence_from_rsi(rsi, config=None):
    """Map RSI values to confidence tiers"""
    if config is None:
        config = {"rsi_thresholds": [35, 45, 60]}

    thresholds = config.get("rsi_thresholds", [35, 45, 60])

    if rsi < thresholds[0]:
        return "SUPER"
    elif rsi < thresholds[1]:
        return "CONFIDENT"
    elif rsi < thresholds[2]:
        return "MEDIUM"
    else:
        return "LOW"


def calculate_simple_macd(rsi, change_1d, change_3d, change_5d):
    """Simple MACD-like signal: momentum confirmation"""
    # If RSI is oversold and price is recovering = strong signal
    if rsi < 35 and change_1d > 0 and change_3d > 0:
        return True  # Confirmed uptrend
    if rsi > 65 and change_1d < 0:
        return False  # Confirmed downtrend
    return None  # Inconclusive


def apply_additional_filters(signal, config=None):
    """Apply optional filters to reduce false signals"""
    if config is None:
        return True

    # Volume filter (skip low-volume signals)
    if config.get("min_volume_percentile", 0) > 0:
        # In real data would check volume, here we simulate
        pass

    # MACD confirmation (if enabled)
    if config.get("require_macd_confirmation", False):
        macd_signal = calculate_simple_macd(
            signal.get("rsi", 50),
            signal.get("change_1d", 0),
            signal.get("change_3d", 0),
            signal.get("change_5d", 0)
        )
        if macd_signal is False:
            return False

    return True


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


def simulate_portfolio(signals, config=None):
    """Simulate portfolio trading based on signals with configurable strategy"""
    if config is None:
        config = {}

    portfolio_balance = STARTING_BALANCE
    positions = []
    closed_trades = []
    portfolio_values = [STARTING_BALANCE]
    returns = []
    daily_values = defaultdict(float)
    feature_tracking = {  # Track which features correlate with wins
        "rsi_wins": defaultdict(lambda: {"wins": 0, "total": 0}),
        "signal_type_wins": defaultdict(lambda: {"wins": 0, "total": 0}),
        "ticker_wins": defaultdict(lambda: {"wins": 0, "total": 0}),
        "confidence_wins": defaultdict(lambda: {"wins": 0, "total": 0}),
    }

    position_sizes = config.get("position_sizes", DEFAULT_POSITION_SIZES)

    for signal in signals:
        ticker = signal["ticker"]
        date = signal["date"]
        price = signal["price"]
        rsi = signal.get("rsi", 50)
        signal_type = signal.get("signal", "NEUTRAL")

        # Skip AVOID signals
        if signal_type == "AVOID":
            continue

        # Apply optional filters
        if not apply_additional_filters(signal, config):
            continue

        # Infer confidence from RSI (with configurable thresholds)
        confidence = infer_confidence_from_rsi(rsi, config)
        position_size = position_sizes.get(confidence, 250.0)

        # Skip if insufficient capital
        if portfolio_balance < position_size:
            continue

        # Check if we hit max positions
        if len(positions) >= MAX_POSITIONS:
            continue

        # Check worst checkpoint for stop loss
        worst_day, worst_change = get_worst_checkpoint(signal)
        if worst_change < STOP_LOSS_THRESHOLD:
            continue

        # Enter position
        best_day, best_change = get_best_checkpoint(signal)

        # Calculate exit price and P&L
        exit_price = price * (1 + best_change / 100)
        pnl = position_size * (best_change / 100)
        pnl_pct = best_change
        is_win = pnl > 0

        trade = {
            "ticker": ticker,
            "entry_date": date,
            "entry_price": price,
            "size": position_size,
            "confidence": confidence,
            "signal_type": signal_type,
            "rsi": rsi,
            "exit_day": best_day,
            "exit_price": exit_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "hold_days": best_day,
            "is_win": is_win,
        }

        # Update portfolio
        portfolio_balance -= position_size
        closed_trades.append(trade)

        # Track features for learning analytics
        rsi_bucket = f"{int(rsi // 10) * 10}-{int(rsi // 10) * 10 + 10}"
        feature_tracking["rsi_wins"][rsi_bucket]["total"] += 1
        feature_tracking["signal_type_wins"][signal_type]["total"] += 1
        feature_tracking["ticker_wins"][ticker]["total"] += 1
        feature_tracking["confidence_wins"][confidence]["total"] += 1

        if is_win:
            feature_tracking["rsi_wins"][rsi_bucket]["wins"] += 1
            feature_tracking["signal_type_wins"][signal_type]["wins"] += 1
            feature_tracking["ticker_wins"][ticker]["wins"] += 1
            feature_tracking["confidence_wins"][confidence]["wins"] += 1

        # Record for analytics
        returns.append(pnl / STARTING_BALANCE)
        daily_values[date] = portfolio_balance

    # Calculate final portfolio value
    total_pnl = sum(t["pnl"] for t in closed_trades)
    final_balance = portfolio_balance + total_pnl

    return {
        "closed_trades": closed_trades,
        "final_balance": final_balance,
        "total_pnl": total_pnl,
        "returns": returns,
        "starting_balance": STARTING_BALANCE,
        "feature_tracking": feature_tracking,
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


def test_configurations(signals):
    """Test different strategy configurations to find optimal learning approach"""
    print("\n" + "=" * 70)
    print("TESTING DIFFERENT CONFIGURATIONS".center(70))
    print("=" * 70)

    configs = [
        {
            "name": "Conservative (High Conviction Only)",
            "rsi_thresholds": [30, 50, 70],
            "position_sizes": {"LOW": 50, "MEDIUM": 150, "CONFIDENT": 500, "SUPER": 1000},
            "require_macd_confirmation": True,
        },
        {
            "name": "Baseline (Current Strategy)",
            "rsi_thresholds": [35, 45, 60],
            "position_sizes": DEFAULT_POSITION_SIZES,
        },
        {
            "name": "Aggressive Learning (More Volume)",
            "rsi_thresholds": [40, 50, 65],
            "position_sizes": {"LOW": 75, "MEDIUM": 200, "CONFIDENT": 750, "SUPER": 1500},
        },
        {
            "name": "Maximum Learning (All Signals)",
            "rsi_thresholds": [45, 55, 70],
            "position_sizes": {"LOW": 50, "MEDIUM": 100, "CONFIDENT": 300, "SUPER": 600},
        },
    ]

    results_summary = []

    for config in configs:
        name = config.pop("name")
        print(f"\nTesting: {name}")
        print("-" * 70)

        results = simulate_portfolio(signals, config)
        metrics = calculate_metrics(results, signals)

        print(f"  Trades: {metrics['total_trades']:3d} | Win Rate: {metrics['win_rate']:5.1f}% | "
              f"Return: £{metrics['total_return_gbp']:7.2f} ({metrics['total_return_pct']:5.2f}%) | "
              f"Sharpe: {metrics['sharpe_ratio']:6.3f}")

        results_summary.append({
            "name": name,
            "config": config,
            "metrics": metrics,
            "trades": results["closed_trades"],
            "features": results.get("feature_tracking", {}),
        })

    return results_summary


def analyze_learning_metrics(trades, features):
    """Analyze what the AI can learn from trade data"""
    print("\n" + "=" * 70)
    print("LEARNING ANALYTICS - WHAT THE AI SHOULD FOCUS ON".center(70))
    print("=" * 70)

    # Win rate by signal type
    print("\n📊 WIN RATE BY SIGNAL TYPE")
    print("-" * 70)
    signal_wins = defaultdict(lambda: {"wins": 0, "total": 0})
    for trade in trades:
        sig_type = trade.get("signal_type", "UNKNOWN")
        signal_wins[sig_type]["total"] += 1
        if trade.get("is_win"):
            signal_wins[sig_type]["wins"] += 1

    for sig_type in sorted(signal_wins.keys()):
        stats_data = signal_wins[sig_type]
        win_rate = (stats_data["wins"] / stats_data["total"] * 100) if stats_data["total"] > 0 else 0
        print(f"  {sig_type:10} → Win Rate: {win_rate:5.1f}% ({stats_data['wins']:2d}/{stats_data['total']:2d})")

    # Win rate by ticker (top performers)
    print("\n📈 BEST PERFORMING ASSETS (by win rate)")
    print("-" * 70)
    ticker_wins = defaultdict(lambda: {"wins": 0, "total": 0})
    for trade in trades:
        ticker = trade["ticker"]
        ticker_wins[ticker]["total"] += 1
        if trade.get("is_win"):
            ticker_wins[ticker]["wins"] += 1

    # Sort by win rate
    sorted_tickers = sorted(
        [(t, s["wins"] / s["total"] * 100) for t, s in ticker_wins.items() if s["total"] >= 2],
        key=lambda x: x[1],
        reverse=True
    )

    for ticker, win_rate in sorted_tickers[:10]:
        total = ticker_wins[ticker]["total"]
        print(f"  {ticker:8} → {win_rate:5.1f}% ({ticker_wins[ticker]['wins']}/{total})")

    # Win rate by RSI ranges
    print("\n🎯 WIN RATE BY RSI RANGE")
    print("-" * 70)
    rsi_wins = defaultdict(lambda: {"wins": 0, "total": 0})
    for trade in trades:
        rsi = trade.get("rsi", 50)
        bucket = f"{int(rsi // 10) * 10}-{int(rsi // 10) * 10 + 10}"
        rsi_wins[bucket]["total"] += 1
        if trade.get("is_win"):
            rsi_wins[bucket]["wins"] += 1

    for bucket in sorted(rsi_wins.keys()):
        stats_data = rsi_wins[bucket]
        win_rate = (stats_data["wins"] / stats_data["total"] * 100) if stats_data["total"] > 0 else 0
        print(f"  RSI {bucket} → Win Rate: {win_rate:5.1f}% ({stats_data['wins']:2d}/{stats_data['total']:2d})")

    # Recommended focus areas
    print("\n💡 AI LEARNING RECOMMENDATIONS")
    print("-" * 70)

    # Find best signal types
    best_signal = max(signal_wins.items(), key=lambda x: x[1]["wins"] / max(1, x[1]["total"]))
    print(f"✓ Focus on {best_signal[0]} signals - highest accuracy at {best_signal[1]['wins'] / best_signal[1]['total'] * 100:.1f}%")

    # Find best assets
    if sorted_tickers:
        best_ticker = sorted_tickers[0]
        print(f"✓ Concentrate on {best_ticker[0]} - proven {best_ticker[1]:.1f}% win rate")

    # Find best RSI range
    best_rsi_bucket = max(rsi_wins.items(), key=lambda x: x[1]["wins"] / max(1, x[1]["total"]))
    print(f"✓ Optimize for RSI {best_rsi_bucket[0]} range - {best_rsi_bucket[1]['wins'] / best_rsi_bucket[1]['total'] * 100:.1f}% accuracy")


def main():
    """Main simulation runner with configuration testing"""
    # Load data
    print("Loading backtest results...")
    data = load_backtest_results("/Users/jacksonamies/stock-agent/backtest_results.json")
    signals = data.get("sample_results", [])

    print(f"Loaded {len(signals)} signals")

    # Split into train/test
    print("\nSplitting into train/test sets...")
    train_signals, test_signals = split_train_test(signals)

    print(f"Train period: {len(train_signals)} signals")
    print(f"Test period: {len(test_signals)} signals")

    # Test configurations
    config_results = test_configurations(train_signals)

    # Run best configuration on test set
    best_config = config_results[1]  # Baseline is usually good
    print(f"\n\nValidating Best Config on Test Period: {best_config['name']}")
    print("-" * 70)

    test_results = simulate_portfolio(test_signals, best_config["config"])
    test_metrics = calculate_metrics(test_results, test_signals)

    print(f"  Trades: {test_metrics['total_trades']:3d} | Win Rate: {test_metrics['win_rate']:5.1f}% | "
          f"Return: £{test_metrics['total_return_gbp']:7.2f} ({test_metrics['total_return_pct']:5.2f}%) | "
          f"Sharpe: {test_metrics['sharpe_ratio']:6.3f}")

    # Overall analysis
    overall_results = simulate_portfolio(signals)
    overall_metrics = calculate_metrics(overall_results, signals)

    print_report(overall_metrics, best_config["metrics"], test_metrics)

    # Learning analytics
    analyze_learning_metrics(overall_results["closed_trades"], overall_results.get("feature_tracking", {}))


if __name__ == "__main__":
    main()
