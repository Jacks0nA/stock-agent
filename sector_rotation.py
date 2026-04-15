"""
Sector Rotation Strategy: Dynamic Sector-Based Positioning

Ranks sectors 1-9 by:
1. Momentum (20-day return)
2. Relative Strength (vs SPY)
3. Mean Reversion (RSI extremes)
4. Volatility (lower is safer)

Integrates into screener scoring:
- Top 3 sectors: +3 score boost
- Bottom 3 sectors: -2 score penalty
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from fetcher import calculate_rsi


class SectorRotationStrategy:
    """Manages dynamic sector rotation and scoring."""

    SECTOR_ETFS = {
        "XLK": "Technology",
        "XLF": "Financials",
        "XLV": "Healthcare",
        "XLY": "Consumer Discretionary",
        "XLE": "Energy",
        "XLI": "Industrials",
        "XLB": "Materials",
        "XLU": "Utilities",
        "XLP": "Consumer Staples"
    }

    def __init__(self):
        self.sector_scores = {}
        self.sector_ranks = {}
        self.allocation = {}

    def get_sector_momentum(self, etf_symbol):
        """
        Calculate sector momentum (20-day return).

        Returns:
            float: 20-day return percentage
        """
        try:
            sector = yf.Ticker(etf_symbol)
            hist = sector.history(period="1mo")

            if len(hist) < 20:
                return 0.0

            price_20d_ago = hist["Close"].iloc[0]
            current_price = hist["Close"].iloc[-1]

            momentum = ((current_price - price_20d_ago) / price_20d_ago) * 100
            return round(momentum, 2)

        except Exception as e:
            return 0.0

    def get_sector_relative_strength(self, etf_symbol):
        """
        Calculate relative strength vs SPY.

        Returns:
            float: Sector return - SPY return (% difference)
        """
        try:
            sector = yf.Ticker(etf_symbol)
            spy = yf.Ticker("SPY")

            sector_hist = sector.history(period="1mo")
            spy_hist = spy.history(period="1mo")

            if len(sector_hist) < 20 or len(spy_hist) < 20:
                return 0.0

            sector_return = ((sector_hist["Close"].iloc[-1] - sector_hist["Close"].iloc[0]) / sector_hist["Close"].iloc[0]) * 100
            spy_return = ((spy_hist["Close"].iloc[-1] - spy_hist["Close"].iloc[0]) / spy_hist["Close"].iloc[0]) * 100

            relative_strength = sector_return - spy_return
            return round(relative_strength, 2)

        except Exception as e:
            return 0.0

    def get_sector_rsi(self, etf_symbol):
        """
        Calculate sector RSI for mean reversion.

        Returns:
            float: RSI value (0-100)
        """
        try:
            sector = yf.Ticker(etf_symbol)
            hist = sector.history(period="3mo")
            hist.index = hist.index.tz_localize(None)

            if len(hist) < 14:
                return 50.0  # Neutral default

            rsi = calculate_rsi(hist["Close"])
            return round(rsi, 1)

        except Exception as e:
            return 50.0

    def get_sector_volatility(self, etf_symbol):
        """
        Calculate sector volatility (20-day std dev).

        Lower volatility = safer sector.

        Returns:
            float: Volatility as percentage
        """
        try:
            sector = yf.Ticker(etf_symbol)
            hist = sector.history(period="1mo")

            if len(hist) < 20:
                return 0.0

            # Calculate daily returns
            returns = hist["Close"].pct_change().dropna()
            volatility = returns.std() * 100

            return round(volatility, 2)

        except Exception as e:
            return 0.0

    def calculate_sector_scores(self):
        """
        Calculate composite score for each sector.

        Score = (Momentum + RS) * RSI_factor - Volatility_penalty

        Returns:
            dict: Sector ETF → composite score
        """
        scores = {}

        for etf, name in self.SECTOR_ETFS.items():
            # Get all metrics
            momentum = self.get_sector_momentum(etf)
            rs = self.get_sector_relative_strength(etf)
            rsi = self.get_sector_rsi(etf)
            volatility = self.get_sector_volatility(etf)

            # RSI factor (oversold = better mean reversion opportunity)
            # RSI < 30 = 1.2x boost (buy signal)
            # RSI 30-70 = 1.0x (neutral)
            # RSI > 70 = 0.8x penalty (overbought)
            if rsi < 30:
                rsi_factor = 1.2
            elif rsi > 70:
                rsi_factor = 0.8
            else:
                rsi_factor = 1.0

            # Volatility penalty (lower is better)
            # Safe sectors (vol < 1.5%) get no penalty
            # Risky sectors (vol > 2.5%) get -1.0 penalty
            vol_penalty = max(0, (volatility - 1.5) * 0.5)

            # Composite score
            composite_score = ((momentum + rs) * rsi_factor) - vol_penalty

            scores[etf] = {
                "score": round(composite_score, 2),
                "momentum": momentum,
                "relative_strength": rs,
                "rsi": rsi,
                "volatility": volatility,
                "name": name
            }

        # Rank by score
        ranked = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)

        self.sector_scores = scores
        self.sector_ranks = {etf: rank + 1 for rank, (etf, _) in enumerate(ranked)}

        return scores

    def get_sector_rank(self, ticker):
        """
        Get sector rank for a ticker (used in screener for scoring).

        Args:
            ticker: Stock ticker

        Returns:
            int: Sector rank 1-9 (1 = best, 9 = worst)
        """
        # This would need a mapping from ticker to sector ETF
        # For now, return default rank 5 (middle)
        # In real usage, integrate with SECTOR_ETFS dict from screener.py

        return 5  # Default neutral rank

    def allocate_portfolio(self, current_positions, capital):
        """
        Recommend portfolio allocation based on sector ranks.

        Args:
            current_positions: List of current positions
            capital: Total capital to allocate

        Returns:
            dict: Sector allocation recommendations
        """
        # Rank sectors first
        self.calculate_sector_scores()

        # Get sorted sectors
        sorted_sectors = sorted(
            self.sector_scores.items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )

        allocation = {}

        for i, (etf, data) in enumerate(sorted_sectors):
            rank = i + 1
            name = data["name"]

            if rank <= 3:
                # Top 3: 40% allocation
                pct_allocation = 40 / 3  # ~13.3% each
                intensity = "🟢 STRONG BUY"
            elif rank <= 6:
                # Middle 3: 35% allocation
                pct_allocation = 35 / 3  # ~11.7% each
                intensity = "⚪ NEUTRAL"
            else:
                # Bottom 3: 25% allocation
                pct_allocation = 25 / 3  # ~8.3% each
                intensity = "🔴 REDUCE"

            allocation[etf] = {
                "rank": rank,
                "name": name,
                "pct_allocation": round(pct_allocation, 1),
                "dollar_amount": round(capital * pct_allocation / 100, 2),
                "intensity": intensity,
                "metrics": data
            }

        self.allocation = allocation
        return allocation

    def get_screener_boost(self, sector_rank):
        """
        Get score boost/penalty for screener based on sector rank.

        Args:
            sector_rank: Sector rank 1-9

        Returns:
            int: Score adjustment (-2 to +3)
        """
        if sector_rank <= 3:
            return 3  # Top 3 sectors: +3 boost
        elif sector_rank <= 6:
            return 0  # Middle: no adjustment
        else:
            return -2  # Bottom 3: -2 penalty


def calculate_sector_scores():
    """Convenience function to calculate all sector scores."""
    strategy = SectorRotationStrategy()
    return strategy.calculate_sector_scores()


def allocate_portfolio(capital=10000, current_positions=None):
    """Convenience function to get portfolio allocation."""
    strategy = SectorRotationStrategy()
    return strategy.allocate_portfolio(current_positions if current_positions is not None else [], capital)


def format_sector_report(allocation_dict):
    """Format sector allocation as readable text."""
    report = f"\n{'='*70}\n"
    report += f"SECTOR ROTATION ALLOCATION\n"
    report += f"{'='*70}\n\n"

    for etf, data in allocation_dict.items():
        rank = data.get("rank", "N/A")
        name = data.get("name", "N/A")
        pct = data.get("pct_allocation", 0)
        intensity = data.get("intensity", "")
        metrics = data.get("metrics", {})

        report += f"{intensity} {rank}. {etf} ({name})\n"
        report += f"   Allocation: {pct}%\n"
        report += f"   Momentum: {metrics.get('momentum', 'N/A')}% | "
        report += f"RS: {metrics.get('relative_strength', 'N/A')}% | "
        report += f"RSI: {metrics.get('rsi', 'N/A')} | "
        report += f"Vol: {metrics.get('volatility', 'N/A')}%\n\n"

    report += f"{'='*70}\n"
    return report
