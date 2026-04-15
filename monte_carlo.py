"""
Monte Carlo Simulation for Stock Recovery Analysis

Runs 10K simulations for each stock to:
1. Estimate recovery probability (will stock recover in 1 year?)
2. Generate return distribution (best case, worst case, median)
3. Calculate confidence intervals (25th, 50th, 75th percentile)
4. Identify highest-probability trades

LEARNING SYSTEM:
- Tracks predictions vs actual results
- Adjusts volatility multiplier based on accuracy
- Gets smarter each day (auto-improves)
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import warnings
from monte_carlo_learning import learning_system

warnings.filterwarnings('ignore')

class MonteCarloSimulator:
    """Runs Monte Carlo simulations for stock price paths."""

    def __init__(self, num_simulations=10000, days_ahead=252):
        """
        Args:
            num_simulations: Number of paths to simulate (default 10K)
            days_ahead: Days to project forward (default 252 = 1 year)
        """
        self.num_simulations = num_simulations
        self.days_ahead = days_ahead

    def get_historical_stats(self, ticker, period="1y"):
        """
        Gets historical volatility and drift from past data.

        Args:
            ticker: Stock ticker
            period: Historical period to analyze

        Returns:
            dict with volatility, drift, current_price, etc.
        """
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            hist.index = hist.index.tz_localize(None)

            if len(hist) < 30:
                return None

            closes = hist["Close"]

            # Calculate returns
            returns = closes.pct_change().dropna()

            # Volatility (annualized)
            volatility = returns.std() * np.sqrt(252)

            # Drift (annualized mean return)
            drift = returns.mean() * 252

            # Current price
            current_price = closes.iloc[-1]

            # Historical support/resistance
            high_52w = closes.tail(252).max()
            low_52w = closes.tail(252).min()

            return {
                "ticker": ticker,
                "current_price": current_price,
                "volatility": volatility,
                "drift": drift,
                "high_52w": high_52w,
                "low_52w": low_52w,
                "returns_mean": returns.mean(),
                "returns_std": returns.std(),
                "success": True
            }
        except Exception as e:
            return None

    def simulate_paths(self, ticker, stats):
        """
        Generates 10K simulated price paths using Geometric Brownian Motion.

        Args:
            ticker: Stock ticker
            stats: Dict from get_historical_stats()

        Returns:
            DataFrame with 10K simulated final prices
        """
        if stats is None or not stats.get("success"):
            return None

        current_price = stats["current_price"]
        volatility = stats["volatility"]
        drift = stats["drift"]

        # LEARNING SYSTEM: Adjust volatility based on past prediction accuracy
        volatility_multiplier = learning_system.volatility_multiplier
        volatility = volatility * volatility_multiplier

        # Handle edge cases
        if volatility == 0 or np.isnan(volatility):
            volatility = 0.2  # Use default
        if np.isnan(drift):
            drift = 0.0

        # Generate random numbers for all simulations
        dt = 1 / 252  # Daily steps
        num_steps = self.days_ahead

        # Initialize paths
        paths = np.zeros((self.num_simulations, num_steps + 1))
        paths[:, 0] = current_price

        # Generate GBM paths
        for step in range(1, num_steps + 1):
            # Random normal returns
            random_returns = np.random.normal(drift * dt, volatility * np.sqrt(dt), self.num_simulations)

            # Apply returns to get next price
            paths[:, step] = paths[:, step - 1] * np.exp(random_returns)

        # Extract final prices (at end of 1 year)
        final_prices = paths[:, -1]

        return final_prices

    def calculate_recovery_probability(self, ticker, current_price, final_prices):
        """
        Calculates probability that stock recovers (returns to current price or higher).

        Args:
            ticker: Stock ticker
            current_price: Current stock price
            final_prices: Array of simulated final prices

        Returns:
            dict with recovery stats
        """
        if final_prices is None:
            return None

        # How many paths recovered?
        recovered = (final_prices >= current_price).sum()
        recovery_probability = recovered / len(final_prices)

        # Calculate return percentiles
        returns = ((final_prices - current_price) / current_price) * 100

        percentile_25 = np.percentile(returns, 25)
        percentile_50 = np.percentile(returns, 50)  # Median
        percentile_75 = np.percentile(returns, 75)

        return {
            "ticker": ticker,
            "recovery_probability": round(recovery_probability, 3),
            "recovery_probability_pct": round(recovery_probability * 100, 1),
            "percentile_25": round(percentile_25, 2),
            "percentile_50": round(percentile_50, 2),
            "percentile_75": round(percentile_75, 2),
            "worst_case": round(np.percentile(final_prices, 1), 2),
            "best_case": round(np.percentile(final_prices, 99), 2),
            "expected_return": round(returns.mean(), 2),
            "downside_risk": round(np.percentile(final_prices, 5), 2),
            "upside_potential": round(np.percentile(final_prices, 95), 2),
        }

    def analyze_stock(self, ticker):
        """
        Full analysis: Get stats → Simulate → Calculate probability.

        Args:
            ticker: Stock ticker

        Returns:
            dict with full Monte Carlo analysis
        """
        # Get historical stats
        stats = self.get_historical_stats(ticker)
        if stats is None:
            return None

        # Simulate price paths
        final_prices = self.simulate_paths(ticker, stats)
        if final_prices is None:
            return None

        # Calculate recovery probability
        recovery_stats = self.calculate_recovery_probability(
            ticker,
            stats["current_price"],
            final_prices
        )

        if recovery_stats is None:
            return None

        # Combine all data
        result = {**stats, **recovery_stats}

        return result

    def get_signal_strength(self, recovery_probability):
        """
        Maps recovery probability to signal strength.

        Args:
            recovery_probability: Probability (0-1)

        Returns:
            str: Signal strength (STRONG, MODERATE, WEAK)
        """
        if recovery_probability > 0.70:
            return "STRONG"
        elif recovery_probability > 0.50:
            return "MODERATE"
        else:
            return "WEAK"

    def batch_analyze(self, tickers):
        """
        Analyzes multiple stocks at once.

        Args:
            tickers: List of tickers

        Returns:
            dict with analysis for each ticker
        """
        results = {}

        for ticker in tickers:
            try:
                analysis = self.analyze_stock(ticker)
                if analysis:
                    results[ticker] = analysis

                    # LEARNING SYSTEM: Log this prediction for later accuracy tracking
                    recovery_prob = analysis.get("recovery_probability", 0)
                    learning_system.record_prediction(ticker, recovery_prob)

            except Exception as e:
                continue

        return results


# Convenience function
def get_monte_carlo_analysis(tickers, num_simulations=10000):
    """
    Quick function to run Monte Carlo analysis on multiple stocks.

    Args:
        tickers: List of stock tickers
        num_simulations: Number of simulations (default 10K)

    Returns:
        dict with analysis results
    """
    simulator = MonteCarloSimulator(num_simulations=num_simulations)
    return simulator.batch_analyze(tickers)


def format_monte_carlo_summary(analysis):
    """
    Formats Monte Carlo analysis into readable text.

    Args:
        analysis: Dict from get_monte_carlo_analysis()

    Returns:
        Formatted string summary
    """
    if not analysis:
        return "No analysis available"

    summary = ""
    for ticker, stats in analysis.items():
        recovery_prob = stats.get("recovery_probability_pct", 0)
        signal = "STRONG ✅" if recovery_prob > 70 else "MODERATE ⚠️" if recovery_prob > 50 else "WEAK ❌"

        summary += f"\n{ticker}:\n"
        summary += f"  Recovery Prob: {recovery_prob}% ({signal})\n"
        summary += f"  Median Return (1yr): {stats.get('percentile_50', 0)}%\n"
        summary += f"  Downside Risk (5th %ile): {stats.get('downside_risk', 0)}\n"
        summary += f"  Upside Potential (95th %ile): {stats.get('upside_potential', 0)}\n"

    return summary
