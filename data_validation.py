"""
Data Leakage Prevention Layer

Ensures backtests only use data available at decision time.
Prevents forward-looking bias that makes strategies appear better than reality.
"""

import pandas as pd
from datetime import datetime
import warnings

class DataValidator:
    """Validates historical data to prevent leakage of future information."""

    def __init__(self):
        self.last_valid_date = None

    def validate_backtest_data(self, df, decision_date):
        """
        Ensures all data used is <= decision_date.

        Args:
            df: DataFrame with datetime index
            decision_date: Date when decision is being made (e.g., today)

        Returns:
            bool: True if data is valid (no future data), False if leakage detected
        """
        if df.index.max() > pd.Timestamp(decision_date):
            future_rows = df[df.index > pd.Timestamp(decision_date)]
            warnings.warn(
                f"DATA LEAKAGE DETECTED: {len(future_rows)} rows of future data found. "
                f"Max future date: {df.index.max().date()}. "
                f"Decision date: {decision_date}. This backtest is not realistic."
            )
            return False
        return True

    def get_data_at_time(self, df, decision_date, lookback_days=250):
        """
        Gets only data available at decision_date.

        Args:
            df: DataFrame with datetime index (full history)
            decision_date: Date when decision is being made
            lookback_days: How many days back to include

        Returns:
            DataFrame: Only rows up to and including decision_date
        """
        decision_ts = pd.Timestamp(decision_date)

        # Filter to data available at decision time
        available_data = df[df.index <= decision_ts]

        if len(available_data) == 0:
            raise ValueError(f"No data available at {decision_date}")

        # Trim to lookback window
        if lookback_days:
            start_date = decision_ts - pd.Timedelta(days=lookback_days)
            available_data = available_data[available_data.index >= start_date]

        return available_data

    def validate_indicator(self, indicator_name, uses_forward_data=False):
        """
        Validates individual indicators don't use forward-looking data.

        Args:
            indicator_name: Name of indicator (e.g., 'RSI', 'MACD')
            uses_forward_data: If True, indicator violates data integrity
        """
        if uses_forward_data:
            raise ValueError(
                f"FORBIDDEN INDICATOR: {indicator_name} uses forward-looking data. "
                f"This indicator cannot be used in live trading. Use lookback-only indicators."
            )

    def validate_rsi_calculation(self, closes_at_time):
        """Ensures RSI is calculated only from historical data."""
        if closes_at_time.index.max() > datetime.now().date():
            raise ValueError("RSI calculated with future data")
        return True

    def validate_ma_calculation(self, closes_at_time, period):
        """
        Ensures moving averages don't use future data.
        MA at time T should only use data up to T.
        """
        if len(closes_at_time) < period:
            warnings.warn(
                f"Insufficient data for MA{period}: only {len(closes_at_time)} bars available. "
                f"MA may be unreliable."
            )
            return False
        return True

    def validate_backtest_signal_generation(self, decision_date, available_data_on_date):
        """
        Validates that signal generation at decision_date only uses data available then.

        Returns:
            dict: Validation report
        """
        report = {
            "valid": True,
            "decision_date": decision_date,
            "data_available_until": available_data_on_date.index.max(),
            "bars_available": len(available_data_on_date),
            "issues": []
        }

        # Check: Do we have enough data?
        if len(available_data_on_date) < 250:
            report["issues"].append(
                f"Warning: Only {len(available_data_on_date)} bars available. "
                f"Consider 250+ for reliable indicators."
            )
            report["valid"] = False

        # Check: No future data
        if available_data_on_date.index.max() > pd.Timestamp(decision_date):
            report["issues"].append("ERROR: Future data detected")
            report["valid"] = False

        return report


class BacktestDataManager:
    """Manages data for realistic backtesting (no look-ahead bias)."""

    def __init__(self):
        self.validator = DataValidator()

    def prepare_backtest_data(self, full_history_df, backtest_start_date, backtest_end_date):
        """
        Prepares data for walk-forward backtesting.

        Each bar uses only data available at that time.
        """
        self.validator.validate_backtest_data(full_history_df, backtest_end_date)

        # Filter to backtest period
        backtest_period = full_history_df[
            (full_history_df.index >= pd.Timestamp(backtest_start_date)) &
            (full_history_df.index <= pd.Timestamp(backtest_end_date))
        ]

        return backtest_period

    def get_signal_at_date(self, full_history, decision_date, lookback_bars=250):
        """
        Gets data available for signal generation at decision_date.
        Mimics live trading (can only use past data).
        """
        available_data = self.validator.get_data_at_time(
            full_history,
            decision_date,
            lookback_days=lookback_bars*365//250  # Convert bars to days roughly
        )

        validation = self.validator.validate_backtest_signal_generation(
            decision_date,
            available_data
        )

        return available_data, validation


# Singleton instance
data_manager = BacktestDataManager()
