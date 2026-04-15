"""
Monte Carlo Learning System

Tracks Monte Carlo predictions vs actual results.
Auto-adjusts parameters based on accuracy.
Gets smarter every day.
"""

import json
import os
from datetime import datetime
from pathlib import Path

LEARNING_FILE = "/tmp/monte_carlo_learning.json"

class MonteCarloLearning:
    """Tracks and learns from Monte Carlo predictions."""

    def __init__(self, learning_file=LEARNING_FILE):
        self.learning_file = learning_file
        self.data = self._load_data()
        self.volatility_multiplier = self._get_current_multiplier()

    def _load_data(self):
        """Loads learning history from file."""
        if os.path.exists(self.learning_file):
            try:
                with open(self.learning_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {"predictions": [], "accuracy_history": []}
        return {"predictions": [], "accuracy_history": []}

    def _save_data(self):
        """Saves learning data to file."""
        try:
            with open(self.learning_file, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass

    def record_prediction(self, ticker, predicted_probability, prediction_date=None):
        """
        Records a Monte Carlo prediction.

        Args:
            ticker: Stock ticker
            predicted_probability: Predicted recovery probability (0-1)
            prediction_date: Date of prediction (default: today)
        """
        if prediction_date is None:
            prediction_date = datetime.now().strftime("%Y-%m-%d")

        prediction = {
            "ticker": ticker,
            "predicted_probability": round(predicted_probability, 3),
            "prediction_date": prediction_date,
            "actual_result": None,
            "actual_return_pct": None,
            "result_date": None,
            "is_correct": None
        }

        self.data["predictions"].append(prediction)
        self._save_data()

    def record_actual_result(self, ticker, actual_return_pct, result_date=None):
        """
        Records actual result for a stock.

        Args:
            ticker: Stock ticker
            actual_return_pct: Actual return percentage (e.g., +15.5)
            result_date: Date of result (default: today)
        """
        if result_date is None:
            result_date = datetime.now().strftime("%Y-%m-%d")

        # Find the most recent prediction for this ticker
        for pred in reversed(self.data["predictions"]):
            if pred["ticker"] == ticker and pred["actual_result"] is None:
                # Did it recover? (positive return)
                recovered = actual_return_pct > 0

                pred["actual_result"] = "RECOVERED" if recovered else "DIDN'T RECOVER"
                pred["actual_return_pct"] = round(actual_return_pct, 2)
                pred["result_date"] = result_date

                # Was prediction correct?
                # High prediction (>70%) + actually recovered = correct
                # Low prediction (<50%) + didn't recover = correct
                if pred["predicted_probability"] > 0.70 and recovered:
                    pred["is_correct"] = True
                elif pred["predicted_probability"] < 0.50 and not recovered:
                    pred["is_correct"] = True
                else:
                    pred["is_correct"] = False

                self._save_data()
                break

    def calculate_accuracy(self):
        """
        Calculates accuracy metrics by prediction confidence level.

        Returns:
            dict with accuracy stats
        """
        completed = [p for p in self.data["predictions"] if p["is_correct"] is not None]

        if not completed:
            return {
                "total_predictions": 0,
                "completed_predictions": 0,
                "overall_accuracy": 0,
                "high_confidence_accuracy": None,
                "medium_confidence_accuracy": None,
                "low_confidence_accuracy": None
            }

        # Split by confidence level
        high_conf = [p for p in completed if p["predicted_probability"] > 0.70]
        medium_conf = [p for p in completed if 0.50 <= p["predicted_probability"] <= 0.70]
        low_conf = [p for p in completed if p["predicted_probability"] < 0.50]

        def calc_acc(predictions):
            if not predictions:
                return None
            correct = sum(1 for p in predictions if p["is_correct"])
            return round(correct / len(predictions), 3)

        return {
            "total_predictions": len(self.data["predictions"]),
            "completed_predictions": len(completed),
            "overall_accuracy": calc_acc(completed),
            "high_confidence_accuracy": calc_acc(high_conf),
            "high_confidence_count": len(high_conf),
            "medium_confidence_accuracy": calc_acc(medium_conf),
            "medium_confidence_count": len(medium_conf),
            "low_confidence_accuracy": calc_acc(low_conf),
            "low_confidence_count": len(low_conf)
        }

    def _get_current_multiplier(self):
        """
        Calculates volatility multiplier based on prediction accuracy.

        Returns:
            float: Multiplier to adjust volatility (1.0 = no change)
        """
        accuracy = self.calculate_accuracy()

        if accuracy["overall_accuracy"] is None:
            return 1.0  # No history yet

        overall_acc = accuracy["overall_accuracy"]
        high_conf_acc = accuracy["high_confidence_accuracy"]

        # If high-confidence predictions are too optimistic (< 70% accuracy)
        # → reduce volatility (be more conservative)
        if high_conf_acc is not None and high_conf_acc < 0.70:
            return 0.85  # Reduce by 15%

        # If high-confidence predictions are too pessimistic (> 85% accuracy)
        # → increase volatility (be more aggressive)
        if high_conf_acc is not None and high_conf_acc > 0.85:
            return 1.15  # Increase by 15%

        # Otherwise, keep same
        return 1.0

    def get_learning_report(self):
        """
        Returns a human-readable learning report.

        Returns:
            str: Formatted report
        """
        accuracy = self.calculate_accuracy()
        multiplier = self.volatility_multiplier

        report = "\n" + "=" * 60
        report += "\nMONTE CARLO LEARNING REPORT\n"
        report += "=" * 60
        report += f"\nTotal Predictions: {accuracy['total_predictions']}\n"
        report += f"Completed (with results): {accuracy['completed_predictions']}\n"

        if accuracy["overall_accuracy"] is None:
            report += "\n⏳ Gathering data... (need 5+ completed predictions)\n"
        else:
            report += f"\n📊 OVERALL ACCURACY: {accuracy['overall_accuracy']*100:.1f}%\n"

            if accuracy["high_confidence_count"] > 0:
                report += f"\n🔥 HIGH CONFIDENCE (>70% pred):\n"
                report += f"   Accuracy: {(accuracy['high_confidence_accuracy']*100 if accuracy['high_confidence_accuracy'] else 0):.1f}%\n"
                report += f"   Count: {accuracy['high_confidence_count']}\n"

            if accuracy["medium_confidence_count"] > 0:
                report += f"\n⚡ MEDIUM CONFIDENCE (50-70% pred):\n"
                report += f"   Accuracy: {(accuracy['medium_confidence_accuracy']*100 if accuracy['medium_confidence_accuracy'] else 0):.1f}%\n"
                report += f"   Count: {accuracy['medium_confidence_count']}\n"

            if accuracy["low_confidence_count"] > 0:
                report += f"\n❄️ LOW CONFIDENCE (<50% pred):\n"
                report += f"   Accuracy: {(accuracy['low_confidence_accuracy']*100 if accuracy['low_confidence_accuracy'] else 0):.1f}%\n"
                report += f"   Count: {accuracy['low_confidence_count']}\n"

        report += f"\n🎯 CURRENT VOLATILITY MULTIPLIER: {multiplier:.2f}x\n"

        if multiplier < 1.0:
            report += f"   → Predictions too optimistic, being more conservative\n"
        elif multiplier > 1.0:
            report += f"   → Predictions too pessimistic, being more aggressive\n"
        else:
            report += f"   → Predictions well-calibrated\n"

        report += "=" * 60 + "\n"

        return report

    def get_monthly_summary(self):
        """
        Gets summary of predictions from the last 30 days.

        Returns:
            dict with monthly stats
        """
        from datetime import datetime, timedelta

        today = datetime.now()
        thirty_days_ago = today - timedelta(days=30)

        recent = [
            p for p in self.data["predictions"]
            if datetime.strptime(p["prediction_date"], "%Y-%m-%d") >= thirty_days_ago
        ]

        completed_recent = [p for p in recent if p["is_correct"] is not None]

        if not completed_recent:
            return {"month_predictions": len(recent), "completed": 0}

        correct = sum(1 for p in completed_recent if p["is_correct"])

        return {
            "month_predictions": len(recent),
            "completed": len(completed_recent),
            "accuracy": round(correct / len(completed_recent), 3),
            "improvement": round((correct / len(completed_recent)) * 100 - 50, 1)  # vs 50% baseline
        }


# Singleton instance
learning_system = MonteCarloLearning()


def log_prediction(ticker, recovery_probability):
    """Quick function to log a prediction."""
    learning_system.record_prediction(ticker, recovery_probability)


def log_result(ticker, actual_return_pct):
    """Quick function to log an actual result."""
    learning_system.record_actual_result(ticker, actual_return_pct)


def get_mc_accuracy():
    """Quick function to get accuracy report."""
    return learning_system.calculate_accuracy()


def print_learning_report():
    """Print learning report to console."""
    print(learning_system.get_learning_report())
