"""
Market Regime Detection: Bull/Bear/Ranging Classification

Analyzes market-wide indicators to determine current regime:
- BULL: Uptrend, low volatility, healthy breadth → Favor growth stocks, larger positions
- BEAR: Downtrend, high volatility, weak breadth → Favor defensive stocks, smaller positions
- RANGING: Sideways, choppy → Favor mean-reversion, range plays

Integrates 3 primary signals:
1. S&P 500 trend (50-day MA vs 200-day MA)
2. Volatility context (VIX level)
3. Market breadth (advancing vs declining stocks)
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


class RegimeDetector:
    """Detects market regime (BULL/BEAR/RANGING)."""

    def __init__(self):
        self.regime = None
        self.confidence = 0.0
        self.breakdown = {}

    def analyze_spy_trend(self):
        """
        Analyze S&P 500 trend using moving averages.

        Returns:
            dict with trend analysis
        """
        try:
            spy = yf.Ticker("SPY")
            hist = spy.history(period="1y")

            if hist.empty or len(hist) < 200:
                return {
                    "metric": "SPY Trend",
                    "status": "UNKNOWN",
                    "value": "Insufficient data",
                    "score": 0,
                    "description": "Not enough historical data"
                }

            # Calculate MAs
            ma50 = hist['Close'].tail(50).mean()
            ma200 = hist['Close'].tail(200).mean()
            current_price = hist['Close'].iloc[-1]

            # Calculate distance from 200MA
            distance_from_200ma = ((current_price - ma200) / ma200) * 100

            # Determine trend
            if ma50 > ma200:
                if distance_from_200ma > 5:
                    status = "STRONG UPTREND"
                    score = 3  # Most bullish
                else:
                    status = "WEAK UPTREND"
                    score = 1
                direction = "UP"
            elif ma50 < ma200:
                if distance_from_200ma < -5:
                    status = "STRONG DOWNTREND"
                    score = -3  # Most bearish
                else:
                    status = "WEAK DOWNTREND"
                    score = -1
                direction = "DOWN"
            else:
                status = "FLAT"
                score = 0
                direction = "FLAT"

            return {
                "metric": "SPY Trend",
                "status": status,
                "value": f"Price {distance_from_200ma:+.1f}% from 200MA",
                "score": score,
                "direction": direction,
                "ma50": round(ma50, 2),
                "ma200": round(ma200, 2),
                "current_price": round(current_price, 2),
                "description": f"50MA ({'above' if ma50 > ma200 else 'below'}) 200MA = {status}"
            }

        except Exception as e:
            return {
                "metric": "SPY Trend",
                "status": "ERROR",
                "value": str(e)[:50],
                "score": 0,
                "description": f"Could not fetch SPY data: {str(e)[:50]}"
            }

    def analyze_volatility(self):
        """
        Analyze market volatility context.

        VIX interpretation:
        - <15: Low volatility, risk-on environment (BULL favorable)
        - 15-20: Normal/moderate volatility
        - >20: High volatility, risk-off (BEAR context)

        Returns:
            dict with volatility analysis
        """
        try:
            vix = yf.Ticker("^VIX")
            hist = vix.history(period="3mo")

            if hist.empty:
                return {
                    "metric": "Volatility (VIX)",
                    "status": "UNKNOWN",
                    "value": "No data",
                    "score": 0,
                    "description": "Could not fetch VIX data"
                }

            current_vix = hist['Close'].iloc[-1]
            vix_20day_avg = hist['Close'].tail(20).mean()

            # Determine volatility regime
            if current_vix < 15:
                status = "LOW"
                score = 2  # Bullish environment
                interpretation = "Risk-on, investors confident"
            elif current_vix < 20:
                status = "MODERATE"
                score = 0  # Neutral
                interpretation = "Normal market volatility"
            else:
                status = "HIGH"
                score = -2  # Bearish environment
                interpretation = "Risk-off, investors cautious"

            # Is VIX rising or falling?
            vix_trend = "Rising" if current_vix > vix_20day_avg else "Falling"

            return {
                "metric": "Volatility (VIX)",
                "status": status,
                "value": f"{current_vix:.1f}",
                "score": score,
                "trend": vix_trend,
                "20day_avg": round(vix_20day_avg, 1),
                "description": f"{status} volatility ({current_vix:.1f}) — {interpretation}"
            }

        except Exception as e:
            return {
                "metric": "Volatility (VIX)",
                "status": "ERROR",
                "value": str(e)[:50],
                "score": 0,
                "description": f"Could not fetch VIX: {str(e)[:50]}"
            }

    def analyze_breadth(self):
        """
        Analyze market breadth (participating stocks).

        Healthy bull markets have >55% of stocks advancing.
        Weak markets have <45% advancing.

        Note: Yahoo Finance doesn't directly provide breadth, so we use
        a proxy based on multiple large-cap indices performance correlation.

        Returns:
            dict with breadth analysis
        """
        try:
            # Proxy: Compare performance of growth (QQQ) vs value (IVE) indices
            # If QQQ significantly outperforms, it's risk-on (broad breadth)
            # If they move together weakly, breadth is poor

            qqq = yf.Ticker("QQQ")
            ive = yf.Ticker("IVE")

            hist_qqq = qqq.history(period="3mo")
            hist_ive = ive.history(period="3mo")

            if hist_qqq.empty or hist_ive.empty:
                return {
                    "metric": "Breadth (Proxy)",
                    "status": "UNKNOWN",
                    "value": "Insufficient data",
                    "score": 0,
                    "description": "Could not calculate breadth proxy"
                }

            # Calculate recent performance (last 20 days)
            qqq_perf = ((hist_qqq['Close'].iloc[-1] - hist_qqq['Close'].iloc[-20]) / hist_qqq['Close'].iloc[-20]) * 100
            ive_perf = ((hist_ive['Close'].iloc[-1] - hist_ive['Close'].iloc[-20]) / hist_ive['Close'].iloc[-20]) * 100

            # Breadth score based on participation
            # Positive performance spread = healthy breadth
            spread = qqq_perf - ive_perf

            if spread > 2:
                status = "HEALTHY"
                score = 2
                breadth_pct = 65  # Estimated
                description = "Growth outperforming, broad participation"
            elif spread > 0:
                status = "MODERATE"
                score = 1
                breadth_pct = 55
                description = "Somewhat healthy participation"
            elif spread > -2:
                status = "WEAK"
                score = -1
                breadth_pct = 45
                description = "Limited participation, narrow market"
            else:
                status = "POOR"
                score = -2
                breadth_pct = 35
                description = "Divergence between growth/value, weak breadth"

            return {
                "metric": "Breadth (Proxy)",
                "status": status,
                "value": f"{breadth_pct}% (estimated)",
                "score": score,
                "qqq_20day_perf": f"{qqq_perf:+.1f}%",
                "ive_20day_perf": f"{ive_perf:+.1f}%",
                "spread": f"{spread:+.1f}%",
                "description": description
            }

        except Exception as e:
            return {
                "metric": "Breadth (Proxy)",
                "status": "ERROR",
                "value": str(e)[:50],
                "score": 0,
                "description": f"Could not calculate breadth: {str(e)[:50]}"
            }

    def detect_regime(self):
        """
        Detect overall market regime by combining all signals.

        Returns:
            dict with regime classification and confidence
        """
        # Analyze all 3 signals
        spy_trend = self.analyze_spy_trend()
        volatility = self.analyze_volatility()
        breadth = self.analyze_breadth()

        # Get scores for decision making
        spy_score = spy_trend.get("score", 0)
        vol_score = volatility.get("score", 0)
        breadth_score = breadth.get("score", 0)

        # Total score (-9 to +9 range)
        total_score = spy_score + vol_score + breadth_score

        # Classify regime
        if total_score >= 4:
            regime = "BULL"
            confidence = min(0.95, 0.5 + (total_score / 18))  # Scale 0.5-0.95
            interpretation = "Strong uptrend, low volatility, healthy breadth — Risk-on environment"
            strategy = "Favor growth/momentum, larger positions (3%), require lower recovery prob (50%+)"

        elif total_score <= -4:
            regime = "BEAR"
            confidence = min(0.95, 0.5 + (abs(total_score) / 18))
            interpretation = "Downtrend, high volatility, weak breadth — Risk-off environment"
            strategy = "Favor defensive/value, smaller positions (1%), require higher recovery prob (75%+)"

        else:
            regime = "RANGING"
            confidence = 0.5 + (abs(total_score) / 18)
            interpretation = "Mixed signals, sideways market — Rotational environment"
            strategy = "Favor mean-reversion, specific price levels, balanced sizing"

        return {
            "regime": regime,
            "confidence": round(confidence, 2),
            "interpretation": interpretation,
            "strategy": strategy,
            "timestamp": datetime.now().isoformat(),
            "signals": {
                "spy_trend": spy_trend,
                "volatility": volatility,
                "breadth": breadth
            },
            "scores": {
                "spy_score": spy_score,
                "vol_score": vol_score,
                "breadth_score": breadth_score,
                "total_score": total_score
            }
        }


# Convenience function
def detect_regime():
    """Quick function to detect current market regime."""
    detector = RegimeDetector()
    return detector.detect_regime()


def format_regime_report(regime_result):
    """Formats regime detection into readable text."""
    regime = regime_result.get("regime", "UNKNOWN")
    confidence = regime_result.get("confidence", 0)
    interpretation = regime_result.get("interpretation", "")
    strategy = regime_result.get("strategy", "")

    report = f"\n{'='*60}\n"
    report += f"MARKET REGIME DETECTION\n"
    report += f"{'='*60}\n"
    report += f"Current Regime: {regime} (Confidence: {confidence*100:.0f}%)\n"
    report += f"Interpretation: {interpretation}\n\n"
    report += f"Strategy: {strategy}\n\n"

    signals = regime_result.get("signals", {})
    if signals:
        report += "Signal Breakdown:\n"
        for signal_name, signal_data in signals.items():
            if isinstance(signal_data, dict):
                metric = signal_data.get("metric", "")
                status = signal_data.get("status", "")
                value = signal_data.get("value", "")
                description = signal_data.get("description", "")
                report += f"  • {metric}: {status} ({value})\n"
                report += f"    → {description}\n"

    report += f"{'='*60}\n"
    return report
