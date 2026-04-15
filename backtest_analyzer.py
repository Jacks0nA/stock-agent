"""
Backtest Analyzer: Advanced Performance Metrics

Calculates risk-adjusted returns from backtest results:
- Sharpe Ratio (return / volatility)
- Sortino Ratio (return / downside volatility)
- Max Drawdown (peak-to-trough decline)
- Profit Factor (gross profit / gross loss)
- Win Rate, Avg Win/Loss, Payoff Ratio

Generates equity curve visualization and monthly performance table.
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime
import os


class BacktestAnalyzer:
    """Analyzes backtest results and calculates performance metrics."""

    def __init__(self):
        self.metrics = {}
        self.equity_curve = []
        self.monthly_returns = {}

    def calculate_sharpe_ratio(self, returns, risk_free_rate=0.02):
        """
        Calculate Sharpe Ratio.

        Sharpe = (mean_return - risk_free_rate) / std_dev
        Interpretation:
        - > 1.0: Excellent (good risk-adjusted returns)
        - 0.5-1.0: Good
        - < 0.5: Poor
        """
        if len(returns) < 2:
            return 0.0

        annual_return = np.mean(returns) * 252  # Annualize daily returns
        annual_volatility = np.std(returns) * np.sqrt(252)

        if annual_volatility == 0:
            return 0.0

        sharpe = (annual_return - risk_free_rate) / annual_volatility
        return round(sharpe, 2)

    def calculate_sortino_ratio(self, returns, risk_free_rate=0.02):
        """
        Calculate Sortino Ratio.

        Similar to Sharpe but only penalizes downside volatility.
        Sortino = (mean_return - risk_free_rate) / downside_std_dev

        Interpretation:
        - > 1.5: Excellent
        - 1.0-1.5: Good
        - < 1.0: Poor
        """
        if len(returns) < 2:
            return 0.0

        annual_return = np.mean(returns) * 252
        downside_returns = np.minimum(returns, 0)
        downside_volatility = np.std(downside_returns) * np.sqrt(252)

        if downside_volatility == 0:
            return 0.0

        sortino = (annual_return - risk_free_rate) / downside_volatility
        return round(sortino, 2)

    def calculate_max_drawdown(self, equity_curve):
        """
        Calculate Maximum Drawdown.

        Max DD = (peak - trough) / peak
        Interpretation:
        - -10% to -20%: Moderate
        - -20% to -50%: Significant
        - < -50%: Severe
        """
        if len(equity_curve) < 2:
            return 0.0

        equity_array = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - running_max) / running_max
        max_dd = np.min(drawdown)

        return round(max_dd * 100, 2)  # Return as percentage

    def calculate_profit_factor(self, trades):
        """
        Calculate Profit Factor.

        Profit Factor = Gross Profit / Gross Loss
        Interpretation:
        - > 2.0: Excellent (profit is 2x the losses)
        - 1.5-2.0: Good
        - 1.0-1.5: Acceptable
        - < 1.0: System is losing
        """
        if not trades or len(trades) == 0:
            return 0.0

        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in trades if t.get("pnl", 0) < 0]

        gross_profit = sum(t["pnl"] for t in winning_trades)
        gross_loss = abs(sum(t["pnl"] for t in losing_trades))

        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0

        profit_factor = gross_profit / gross_loss
        return round(profit_factor, 2)

    def analyze_backtest_results(self, backtest_json_path=None):
        """
        Analyze backtest results from JSON file.

        Args:
            backtest_json_path: Path to backtest_results.json

        Returns:
            dict with comprehensive metrics
        """
        try:
            if backtest_json_path is None:
                backtest_json_path = "/Users/jacksonamies/stock-agent/backtest_results.json"

            if not os.path.exists(backtest_json_path):
                return {
                    "error": "Backtest results file not found",
                    "path": backtest_json_path
                }

            with open(backtest_json_path, 'r') as f:
                backtest_data = json.load(f)

            # Extract key metrics from backtest
            total_trades = backtest_data.get("total_trades", 0)
            winning_trades = backtest_data.get("winning_trades", 0)
            losing_trades = backtest_data.get("losing_trades", 0)
            win_rate = backtest_data.get("win_rate", 0)

            # Calculate P&L metrics
            total_profit = backtest_data.get("total_profit", 0)
            total_loss = backtest_data.get("total_loss", 0)
            net_pnl = total_profit - abs(total_loss)

            # Reconstruct returns (approximate from trades)
            trades = backtest_data.get("trades", [])
            returns = []
            daily_pnl = 0

            if trades:
                for trade in trades:
                    pnl_pct = trade.get("pnl_pct", 0)
                    returns.append(pnl_pct / 100)  # Convert to decimal
                    daily_pnl += trade.get("pnl", 0)

                # Build equity curve
                equity_curve = [10000]  # Starting capital assumption
                for ret in returns:
                    equity_curve.append(equity_curve[-1] * (1 + ret))

                self.equity_curve = equity_curve
            else:
                returns = []
                equity_curve = [10000]

            # Calculate metrics
            sharpe = self.calculate_sharpe_ratio(returns) if returns else 0
            sortino = self.calculate_sortino_ratio(returns) if returns else 0
            max_dd = self.calculate_max_drawdown(equity_curve)
            profit_factor = self.calculate_profit_factor(trades)

            # Regime-specific analysis
            bull_trades = [t for t in trades if t.get("regime") == "BULL"]
            bear_trades = [t for t in trades if t.get("regime") == "BEAR"]

            bull_win_rate = (len([t for t in bull_trades if t.get("pnl", 0) > 0]) / len(bull_trades) * 100) if bull_trades else 0
            bear_win_rate = (len([t for t in bear_trades if t.get("pnl", 0) > 0]) / len(bear_trades) * 100) if bear_trades else 0

            self.metrics = {
                "summary": {
                    "total_trades": total_trades,
                    "winning_trades": winning_trades,
                    "losing_trades": losing_trades,
                    "win_rate": f"{win_rate:.1f}%",
                    "net_pnl": f"£{net_pnl:.2f}",
                    "total_profit": f"£{total_profit:.2f}",
                    "total_loss": f"£{abs(total_loss):.2f}"
                },
                "risk_adjusted_returns": {
                    "sharpe_ratio": sharpe,
                    "sortino_ratio": sortino,
                    "max_drawdown": f"{max_dd:.2f}%",
                    "profit_factor": profit_factor
                },
                "regime_analysis": {
                    "bull_trades": len(bull_trades),
                    "bear_trades": len(bear_trades),
                    "bull_win_rate": f"{bull_win_rate:.1f}%",
                    "bear_win_rate": f"{bear_win_rate:.1f}%"
                },
                "performance_summary": {
                    "avg_win": f"£{(total_profit / max(winning_trades, 1)):.2f}",
                    "avg_loss": f"£{abs(total_loss) / max(losing_trades, 1):.2f}",
                    "payoff_ratio": round((total_profit / max(winning_trades, 1)) / (abs(total_loss) / max(losing_trades, 1)) if losing_trades > 0 else 0, 2)
                }
            }

            return self.metrics

        except Exception as e:
            return {"error": str(e)[:100]}

    def generate_backtest_report(self, backtest_json_path=None):
        """
        Generate formatted backtest report.

        Returns:
            Formatted string for display
        """
        metrics = self.analyze_backtest_results(backtest_json_path)

        if "error" in metrics:
            return f"❌ Error: {metrics['error']}"

        report = f"\n{'='*70}\n"
        report += f"BACKTEST PERFORMANCE ANALYSIS\n"
        report += f"{'='*70}\n\n"

        # Summary Stats
        summary = metrics.get("summary", {})
        report += f"📊 SUMMARY STATS\n"
        report += f"  Total Trades: {summary.get('total_trades', 0)}\n"
        report += f"  Winners: {summary.get('winning_trades', 0)} | Losers: {summary.get('losing_trades', 0)}\n"
        report += f"  Win Rate: {summary.get('win_rate', 'N/A')}\n"
        report += f"  Net P&L: {summary.get('net_pnl', 'N/A')}\n"
        report += f"  Gross Profit: {summary.get('total_profit', 'N/A')} | Gross Loss: {summary.get('total_loss', 'N/A')}\n\n"

        # Risk-Adjusted Returns
        rar = metrics.get("risk_adjusted_returns", {})
        report += f"📈 RISK-ADJUSTED RETURNS\n"
        report += f"  Sharpe Ratio: {rar.get('sharpe_ratio', 'N/A')} (>1.0 = excellent)\n"
        report += f"  Sortino Ratio: {rar.get('sortino_ratio', 'N/A')} (>1.5 = excellent)\n"
        report += f"  Max Drawdown: {rar.get('max_drawdown', 'N/A')} (peak-to-trough)\n"
        report += f"  Profit Factor: {rar.get('profit_factor', 'N/A')} (>1.5 = good)\n\n"

        # Regime Analysis
        regime = metrics.get("regime_analysis", {})
        report += f"🎯 REGIME ANALYSIS\n"
        report += f"  BULL Market Trades: {regime.get('bull_trades', 0)} | Win Rate: {regime.get('bull_win_rate', 'N/A')}\n"
        report += f"  BEAR Market Trades: {regime.get('bear_trades', 0)} | Win Rate: {regime.get('bear_win_rate', 'N/A')}\n\n"

        # Performance Summary
        perf = metrics.get("performance_summary", {})
        report += f"💰 PER-TRADE METRICS\n"
        report += f"  Avg Win: {perf.get('avg_win', 'N/A')}\n"
        report += f"  Avg Loss: {perf.get('avg_loss', 'N/A')}\n"
        report += f"  Payoff Ratio: {perf.get('payoff_ratio', 'N/A')} (win/loss ratio)\n\n"

        report += f"{'='*70}\n"

        return report


def format_backtest_report(backtest_json_path=None):
    """Convenience function to generate backtest report."""
    analyzer = BacktestAnalyzer()
    return analyzer.generate_backtest_report(backtest_json_path)


def get_backtest_metrics(backtest_json_path=None):
    """Convenience function to get backtest metrics as dict."""
    analyzer = BacktestAnalyzer()
    return analyzer.analyze_backtest_results(backtest_json_path)
