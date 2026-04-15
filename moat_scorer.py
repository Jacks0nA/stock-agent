"""
Moat Scoring System: Competitive Advantage Analysis

Analyzes 5 dimensions of competitive moats to produce a 0-5 score:
1. Profitability (Net Margin vs competitors)
2. Return on Equity (Capital efficiency)
3. Free Cash Flow Strength (Sustainability)
4. Revenue Growth Consistency (Market position)
5. Balance Sheet Strength (Financial moat)

Higher score = Stronger, more defensible business with sustainable advantages.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


class MoatScorer:
    """Calculates competitive moat strength (0-5 scale)."""

    def __init__(self):
        self.ticker = None
        self.dimensions = {}
        self.breakdown = {}

    def score_profitability_moat(self, ticker_obj):
        """
        Dimension 1: Profitability Moat (Net Margin)

        High margins = pricing power = competitive advantage.
        Benchmarks based on industry norms:
        - Tech/SaaS: 15%+ is normal (higher thresholds)
        - Retail/Services: 5-10% is normal
        - Average: 10% is respectable
        """
        try:
            profit_margin = ticker_obj.info.get('profitMargins', None)

            if profit_margin is None:
                return {"dimension": "Profitability", "score": 2, "value": "Unknown", "reason": "Data unavailable"}

            margin_pct = profit_margin * 100

            if margin_pct > 20:
                score = 5
                reason = f"Extremely profitable at {margin_pct:.1f}% margin"
            elif margin_pct > 15:
                score = 4
                reason = f"Strong margin at {margin_pct:.1f}%"
            elif margin_pct > 10:
                score = 3
                reason = f"Healthy margin at {margin_pct:.1f}%"
            elif margin_pct > 5:
                score = 2
                reason = f"Moderate margin at {margin_pct:.1f}%"
            else:
                score = 1
                reason = f"Low margin at {margin_pct:.1f}%"

            return {
                "dimension": "Profitability",
                "score": score,
                "value": f"{margin_pct:.1f}%",
                "reason": reason
            }
        except Exception as e:
            return {"dimension": "Profitability", "score": 2, "value": "Error", "reason": str(e)[:50]}

    def score_roe_moat(self, ticker_obj):
        """
        Dimension 2: Return on Equity (ROE)

        High ROE = capital efficiently deployed = strong competitive position.
        Benchmarks:
        - >25%: Exceptional (best-in-class businesses)
        - 15-25%: Strong (sustainable advantage)
        - 10-15%: Decent
        - <10%: Weak capital efficiency
        """
        try:
            roe = ticker_obj.info.get('returnOnEquity', None)

            if roe is None:
                return {"dimension": "Return on Equity", "score": 2, "value": "Unknown", "reason": "Data unavailable"}

            roe_pct = roe * 100

            if roe_pct > 25:
                score = 5
                reason = f"Exceptional ROE at {roe_pct:.1f}%"
            elif roe_pct > 20:
                score = 4
                reason = f"Strong ROE at {roe_pct:.1f}%"
            elif roe_pct > 15:
                score = 3
                reason = f"Decent ROE at {roe_pct:.1f}%"
            elif roe_pct > 10:
                score = 2
                reason = f"Moderate ROE at {roe_pct:.1f}%"
            else:
                score = 1
                reason = f"Weak ROE at {roe_pct:.1f}%"

            return {
                "dimension": "Return on Equity",
                "score": score,
                "value": f"{roe_pct:.1f}%",
                "reason": reason
            }
        except Exception as e:
            return {"dimension": "Return on Equity", "score": 2, "value": "Error", "reason": str(e)[:50]}

    def score_fcf_moat(self, ticker_obj):
        """
        Dimension 3: Free Cash Flow Strength

        Sustainable business model = strong FCF conversion.
        FCF = Operating CF - Capital Expenditures (CapEx)
        Benchmark: FCF as % of revenue
        """
        try:
            stock = ticker_obj
            financials = stock.quarterly_financials if hasattr(stock, 'quarterly_financials') else None

            if financials is None or financials.empty:
                return {"dimension": "Free Cash Flow", "score": 2, "value": "Unknown", "reason": "Financial data unavailable"}

            # Get most recent quarter
            ocf = financials.loc['Operating Cash Flow'].iloc[0] if 'Operating Cash Flow' in financials.index else None
            revenue = financials.loc['Total Revenue'].iloc[0] if 'Total Revenue' in financials.index else None

            # Estimate CapEx (approximation: typically 3-5% of revenue for most companies)
            # Without explicit CapEx data, use conservative estimate
            estimated_capex = revenue * 0.04 if revenue else 0

            if ocf is None or revenue is None or revenue == 0:
                return {"dimension": "Free Cash Flow", "score": 2, "value": "Unknown", "reason": "Insufficient data"}

            fcf = ocf - estimated_capex
            fcf_pct = (fcf / revenue * 100) if revenue != 0 else 0

            if fcf_pct > 15:
                score = 5
                reason = f"Very strong FCF at {fcf_pct:.1f}% of revenue"
            elif fcf_pct > 10:
                score = 4
                reason = f"Strong FCF at {fcf_pct:.1f}% of revenue"
            elif fcf_pct > 5:
                score = 3
                reason = f"Healthy FCF at {fcf_pct:.1f}% of revenue"
            elif fcf_pct > 0:
                score = 2
                reason = f"Modest FCF at {fcf_pct:.1f}% of revenue"
            else:
                score = 1
                reason = f"Negative/weak FCF at {fcf_pct:.1f}% of revenue"

            return {
                "dimension": "Free Cash Flow",
                "score": score,
                "value": f"{fcf_pct:.1f}% of revenue",
                "reason": reason
            }
        except Exception as e:
            return {"dimension": "Free Cash Flow", "score": 2, "value": "Error", "reason": str(e)[:50]}

    def score_revenue_growth(self, ticker_obj):
        """
        Dimension 4: Revenue Growth Consistency

        Growing revenue = expanding market share = stronger position.
        CAGR over 2 years is the metric.
        """
        try:
            stock = ticker_obj
            financials = stock.quarterly_financials if hasattr(stock, 'quarterly_financials') else None

            if financials is None or financials.empty:
                return {"dimension": "Revenue Growth", "score": 2, "value": "Unknown", "reason": "Financial data unavailable"}

            if 'Total Revenue' not in financials.index:
                return {"dimension": "Revenue Growth", "score": 2, "value": "Unknown", "reason": "Revenue data unavailable"}

            revenue_data = financials.loc['Total Revenue']

            # Get data for last 2 years (8 quarters)
            if len(revenue_data) < 8:
                # Not enough quarters, use what we have
                if len(revenue_data) >= 2:
                    oldest_revenue = revenue_data.iloc[-1]
                    newest_revenue = revenue_data.iloc[0]
                    quarters = len(revenue_data) - 1
                    years = quarters / 4.0
                else:
                    return {"dimension": "Revenue Growth", "score": 2, "value": "Unknown", "reason": "Insufficient historical data"}
            else:
                oldest_revenue = revenue_data.iloc[7]
                newest_revenue = revenue_data.iloc[0]
                years = 2.0

            if oldest_revenue <= 0:
                return {"dimension": "Revenue Growth", "score": 2, "value": "Unknown", "reason": "Invalid historical revenue"}

            # Calculate CAGR
            cagr = ((newest_revenue / oldest_revenue) ** (1.0 / years) - 1) * 100

            if cagr > 15:
                score = 5
                reason = f"Strong growth at {cagr:.1f}% CAGR"
            elif cagr > 10:
                score = 4
                reason = f"Good growth at {cagr:.1f}% CAGR"
            elif cagr > 5:
                score = 3
                reason = f"Modest growth at {cagr:.1f}% CAGR"
            elif cagr > 0:
                score = 2
                reason = f"Slow growth at {cagr:.1f}% CAGR"
            else:
                score = 1
                reason = f"Declining revenue at {cagr:.1f}% CAGR"

            return {
                "dimension": "Revenue Growth",
                "score": score,
                "value": f"{cagr:.1f}% CAGR",
                "reason": reason
            }
        except Exception as e:
            return {"dimension": "Revenue Growth", "score": 2, "value": "Error", "reason": str(e)[:50]}

    def score_balance_sheet_strength(self, ticker_obj):
        """
        Dimension 5: Balance Sheet Strength

        Low debt = ability to survive downturns = financial moat.
        Debt-to-Equity ratio benchmark.
        """
        try:
            debt_to_equity = ticker_obj.info.get('debtToEquity', None)

            if debt_to_equity is None:
                return {"dimension": "Balance Sheet", "score": 2, "value": "Unknown", "reason": "Data unavailable"}

            if debt_to_equity < 0.5:
                score = 5
                reason = f"Very strong balance sheet (D/E: {debt_to_equity:.2f})"
            elif debt_to_equity < 1.0:
                score = 4
                reason = f"Strong balance sheet (D/E: {debt_to_equity:.2f})"
            elif debt_to_equity < 1.5:
                score = 3
                reason = f"Moderate balance sheet (D/E: {debt_to_equity:.2f})"
            elif debt_to_equity < 2.0:
                score = 2
                reason = f"Elevated leverage (D/E: {debt_to_equity:.2f})"
            else:
                score = 1
                reason = f"High leverage (D/E: {debt_to_equity:.2f})"

            return {
                "dimension": "Balance Sheet",
                "score": score,
                "value": f"{debt_to_equity:.2f}",
                "reason": reason
            }
        except Exception as e:
            return {"dimension": "Balance Sheet", "score": 2, "value": "Error", "reason": str(e)[:50]}

    def score_moat(self, ticker):
        """
        Calculate overall moat score (0-5) by averaging 5 dimensions.

        Args:
            ticker: Stock ticker symbol

        Returns:
            dict with score (0-5), breakdown of each dimension, and interpretations
        """
        try:
            self.ticker = ticker.upper()
            stock = yf.Ticker(self.ticker)

            # Score all 5 dimensions
            profitability = self.score_profitability_moat(stock)
            roe = self.score_roe_moat(stock)
            fcf = self.score_fcf_moat(stock)
            growth = self.score_revenue_growth(stock)
            balance_sheet = self.score_balance_sheet_strength(stock)

            # Calculate average moat score
            scores = [
                profitability["score"],
                roe["score"],
                fcf["score"],
                growth["score"],
                balance_sheet["score"]
            ]

            average_score = sum(scores) / len(scores)

            # Interpretation
            if average_score >= 4.5:
                strength = "EXCEPTIONAL"
                interpretation = "Fortress-like competitive advantage, best-in-class business"
            elif average_score >= 3.5:
                strength = "STRONG"
                interpretation = "Clear competitive moat, defensible market position"
            elif average_score >= 2.5:
                strength = "MODERATE"
                interpretation = "Some competitive advantages but not exceptional"
            elif average_score >= 1.5:
                strength = "WEAK"
                interpretation = "Limited competitive moat, vulnerable to competition"
            else:
                strength = "VERY WEAK"
                interpretation = "Commoditized business, easily replicated"

            return {
                "ticker": self.ticker,
                "moat_score": round(average_score, 2),
                "strength": strength,
                "interpretation": interpretation,
                "dimensions": {
                    "profitability": profitability,
                    "roe": roe,
                    "fcf": fcf,
                    "growth": growth,
                    "balance_sheet": balance_sheet
                },
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "ticker": ticker.upper(),
                "moat_score": 2.5,
                "strength": "UNKNOWN",
                "interpretation": f"Could not calculate moat score: {str(e)[:100]}",
                "dimensions": {},
                "error": str(e)[:100]
            }


# Convenience function
def score_moat(ticker):
    """Quick function to score moat for a single stock."""
    scorer = MoatScorer()
    return scorer.score_moat(ticker)


def format_moat_report(moat_result):
    """Formats moat score into readable text."""
    ticker = moat_result.get("ticker", "UNKNOWN")
    score = moat_result.get("moat_score", 0)
    strength = moat_result.get("strength", "UNKNOWN")
    interpretation = moat_result.get("interpretation", "")

    report = f"\n{'='*60}\n"
    report += f"MOAT ANALYSIS: {ticker}\n"
    report += f"{'='*60}\n"
    report += f"Moat Score: {score}/5.0 — {strength}\n"
    report += f"Interpretation: {interpretation}\n\n"

    dimensions = moat_result.get("dimensions", {})
    if dimensions:
        report += "Dimension Breakdown:\n"
        for dim_name, dim_data in dimensions.items():
            if isinstance(dim_data, dict):
                dim_score = dim_data.get("score", "N/A")
                dim_value = dim_data.get("value", "N/A")
                dim_reason = dim_data.get("reason", "")
                report += f"  • {dim_name.replace('_', ' ').title()}: {dim_score}/5 ({dim_value})\n"
                report += f"    → {dim_reason}\n"

    report += f"{'='*60}\n"
    return report
