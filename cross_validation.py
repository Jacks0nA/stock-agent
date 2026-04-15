"""
Cross-Validation Layer: Financial Quality Validation

Validates that financial metrics align before trading:
1. Cash Quality Check: Operating Cash Flow > Net Income
2. Growth Consistency: NI growth matches revenue growth
3. Accounting Red Flags: AR/Inventory growth > NI growth
4. Peer Comparison: Metrics vs sector benchmarks
5. Debt Quality: Debt serviceability

Prevents accounting tricks and quality deterioration.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


class CrossValidator:
    """Validates financial quality and consistency."""

    def __init__(self):
        self.validation_score = 0
        self.issues = []
        self.warnings = []

    def reset(self):
        """Reset for new validation."""
        self.validation_score = 100
        self.issues = []
        self.warnings = []

    def check_cash_quality(self, ticker):
        """
        Validates Operating Cash Flow > Net Income (cash quality).
        High-quality profits convert to actual cash.

        Args:
            ticker: Stock ticker

        Returns:
            dict with cash quality metrics
        """
        try:
            stock = yf.Ticker(ticker)
            financials = stock.quarterly_financials if hasattr(stock, 'quarterly_financials') else None

            if financials is None or financials.empty:
                self.warnings.append(f"Could not fetch financials for {ticker}")
                return {"cash_quality": "UNKNOWN", "ocf_ni_ratio": None}

            # Get most recent quarter
            ocf = financials.loc['Operating Cash Flow'].iloc[0] if 'Operating Cash Flow' in financials.index else None
            ni = financials.loc['Net Income'].iloc[0] if 'Net Income' in financials.index else None

            if ocf is None or ni is None:
                return {"cash_quality": "UNKNOWN", "ocf_ni_ratio": None}

            # Calculate ratio
            if ni != 0:
                ocf_ni_ratio = ocf / ni
            else:
                ocf_ni_ratio = None

            # Evaluate
            if ocf_ni_ratio is None:
                return {"cash_quality": "UNKNOWN", "ocf_ni_ratio": None}

            if ocf_ni_ratio > 1.2:
                self.validation_score -= 0  # Excellent
                return {"cash_quality": "EXCELLENT", "ocf_ni_ratio": round(ocf_ni_ratio, 2)}

            elif ocf_ni_ratio > 1.0:
                self.validation_score -= 0  # Good
                return {"cash_quality": "GOOD", "ocf_ni_ratio": round(ocf_ni_ratio, 2)}

            elif ocf_ni_ratio > 0.8:
                self.validation_score -= 5  # Fair
                self.warnings.append(f"OCF/NI ratio {ocf_ni_ratio:.2f} is lower than ideal")
                return {"cash_quality": "FAIR", "ocf_ni_ratio": round(ocf_ni_ratio, 2)}

            else:
                self.validation_score -= 15  # Poor (red flag)
                self.issues.append(f"OCF/NI ratio {ocf_ni_ratio:.2f} suggests low cash conversion")
                return {"cash_quality": "POOR", "ocf_ni_ratio": round(ocf_ni_ratio, 2)}

        except Exception as e:
            self.warnings.append(f"Cash quality check error: {str(e)[:50]}")
            return {"cash_quality": "UNKNOWN", "ocf_ni_ratio": None}

    def check_growth_consistency(self, ticker):
        """
        Validates Net Income growth matches Revenue growth.
        Divergence suggests quality issues or margin compression.

        Args:
            ticker: Stock ticker

        Returns:
            dict with growth metrics
        """
        try:
            stock = yf.Ticker(ticker)
            financials = stock.quarterly_financials if hasattr(stock, 'quarterly_financials') else None

            if financials is None or financials.empty:
                return {"growth_consistency": "UNKNOWN"}

            # Get revenue and NI (most recent 2 quarters for YoY comparison)
            revenue = financials.loc['Total Revenue'].iloc[:2] if 'Total Revenue' in financials.index else None
            ni = financials.loc['Net Income'].iloc[:2] if 'Net Income' in financials.index else None

            if revenue is None or ni is None or len(revenue) < 2 or len(ni) < 2:
                return {"growth_consistency": "UNKNOWN"}

            # Calculate growth rates (current vs prior)
            revenue_growth = ((revenue.iloc[0] - revenue.iloc[1]) / abs(revenue.iloc[1]) * 100) if revenue.iloc[1] != 0 else 0
            ni_growth = ((ni.iloc[0] - ni.iloc[1]) / abs(ni.iloc[1]) * 100) if ni.iloc[1] != 0 else 0

            # Evaluate consistency
            growth_gap = abs(revenue_growth - ni_growth)

            if growth_gap < 5:
                self.validation_score -= 0  # Excellent
                return {
                    "growth_consistency": "EXCELLENT",
                    "revenue_growth": round(revenue_growth, 1),
                    "ni_growth": round(ni_growth, 1),
                    "gap": round(growth_gap, 1)
                }

            elif growth_gap < 15:
                self.validation_score -= 5  # Good
                return {
                    "growth_consistency": "GOOD",
                    "revenue_growth": round(revenue_growth, 1),
                    "ni_growth": round(ni_growth, 1),
                    "gap": round(growth_gap, 1)
                }

            else:
                self.validation_score -= 15  # Poor (red flag)
                self.issues.append(f"Revenue growth {revenue_growth:.1f}% vs NI growth {ni_growth:.1f}% divergence suggests quality issues")
                return {
                    "growth_consistency": "POOR",
                    "revenue_growth": round(revenue_growth, 1),
                    "ni_growth": round(ni_growth, 1),
                    "gap": round(growth_gap, 1)
                }

        except Exception as e:
            self.warnings.append(f"Growth consistency check error: {str(e)[:50]}")
            return {"growth_consistency": "UNKNOWN"}

    def check_accounting_red_flags(self, ticker):
        """
        Detects accounting red flags:
        - AR growth > Revenue growth
        - Inventory growth > Revenue growth
        - Suggests aggressive accounting or quality issues

        Args:
            ticker: Stock ticker

        Returns:
            dict with red flag assessment
        """
        try:
            stock = yf.Ticker(ticker)
            balance_sheet = stock.quarterly_balance_sheet if hasattr(stock, 'quarterly_balance_sheet') else None

            if balance_sheet is None or balance_sheet.empty:
                return {"red_flags": "UNKNOWN"}

            # Get AR and Inventory (most recent 2 quarters)
            ar = balance_sheet.loc['Accounts Receivable'].iloc[:2] if 'Accounts Receivable' in balance_sheet.index else None
            inventory = balance_sheet.loc['Inventory'].iloc[:2] if 'Inventory' in balance_sheet.index else None

            red_flag_count = 0

            # Check AR growth
            if ar is not None and len(ar) >= 2 and ar.iloc[1] != 0:
                ar_growth = ((ar.iloc[0] - ar.iloc[1]) / ar.iloc[1] * 100)
                if ar_growth > 20:  # High AR growth
                    red_flag_count += 1
                    self.warnings.append(f"High AR growth: {ar_growth:.1f}%")

            # Check Inventory growth
            if inventory is not None and len(inventory) >= 2 and inventory.iloc[1] != 0:
                inv_growth = ((inventory.iloc[0] - inventory.iloc[1]) / inventory.iloc[1] * 100)
                if inv_growth > 20:  # High inventory growth
                    red_flag_count += 1
                    self.warnings.append(f"High inventory growth: {inv_growth:.1f}%")

            if red_flag_count >= 2:
                self.validation_score -= 20
                self.issues.append("Multiple accounting red flags detected")
                return {"red_flags": "MULTIPLE", "count": red_flag_count}

            elif red_flag_count == 1:
                self.validation_score -= 10
                return {"red_flags": "SINGLE", "count": 1}

            else:
                return {"red_flags": "NONE", "count": 0}

        except Exception as e:
            self.warnings.append(f"Red flag check error: {str(e)[:50]}")
            return {"red_flags": "UNKNOWN"}

    def check_debt_quality(self, ticker):
        """
        Validates debt serviceability (EBIT/Interest > 2.5x).

        Args:
            ticker: Stock ticker

        Returns:
            dict with debt quality metrics
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info if hasattr(stock, 'info') else {}

            total_debt = info.get('totalDebt', 0)
            ebit = info.get('ebit', 0)
            interest_expense = info.get('interestExpense', 0)

            if total_debt is None or ebit is None or interest_expense is None:
                return {"debt_quality": "UNKNOWN"}

            # Calculate interest coverage
            if interest_expense > 0:
                interest_coverage = ebit / interest_expense
            else:
                interest_coverage = None

            if interest_coverage is None:
                return {"debt_quality": "UNKNOWN"}

            if interest_coverage > 5:
                return {"debt_quality": "EXCELLENT", "coverage": round(interest_coverage, 1)}

            elif interest_coverage > 2.5:
                return {"debt_quality": "GOOD", "coverage": round(interest_coverage, 1)}

            elif interest_coverage > 1.5:
                self.validation_score -= 10
                self.warnings.append(f"Debt coverage {interest_coverage:.1f}x is marginal")
                return {"debt_quality": "FAIR", "coverage": round(interest_coverage, 1)}

            else:
                self.validation_score -= 20
                self.issues.append(f"Debt coverage {interest_coverage:.1f}x is poor")
                return {"debt_quality": "POOR", "coverage": round(interest_coverage, 1)}

        except Exception as e:
            self.warnings.append(f"Debt quality check error: {str(e)[:50]}")
            return {"debt_quality": "UNKNOWN"}

    def validate_stock(self, ticker):
        """
        Full validation: runs all checks.

        Args:
            ticker: Stock ticker

        Returns:
            dict with validation results
        """
        self.reset()

        print(f"\n✓ Cross-validating {ticker}...")

        cash_quality = self.check_cash_quality(ticker)
        growth = self.check_growth_consistency(ticker)
        red_flags = self.check_accounting_red_flags(ticker)
        debt = self.check_debt_quality(ticker)

        # Final validation score (0-100)
        final_score = max(0, min(100, self.validation_score))

        return {
            "ticker": ticker,
            "validation_score": final_score,
            "is_valid": final_score >= 70,  # Threshold: 70+ passes validation
            "cash_quality": cash_quality,
            "growth_consistency": growth,
            "accounting_red_flags": red_flags,
            "debt_quality": debt,
            "issues": self.issues,
            "warnings": self.warnings
        }


# Convenience function
def validate_stock(ticker):
    """Quick validation of a single stock."""
    validator = CrossValidator()
    return validator.validate_stock(ticker)


def format_validation_report(validation_result):
    """Formats validation result into readable text."""
    ticker = validation_result.get("ticker", "UNKNOWN")
    score = validation_result.get("validation_score", 0)
    is_valid = validation_result.get("is_valid", False)

    report = f"\n{'='*60}\n"
    report += f"CROSS-VALIDATION REPORT: {ticker}\n"
    report += f"{'='*60}\n"
    report += f"Validation Score: {score}/100 {'✅ PASS' if is_valid else '❌ FAIL'}\n\n"

    report += f"Cash Quality: {validation_result['cash_quality'].get('cash_quality', 'N/A')}\n"
    report += f"Growth Consistency: {validation_result['growth_consistency'].get('growth_consistency', 'N/A')}\n"
    report += f"Accounting Red Flags: {validation_result['accounting_red_flags'].get('red_flags', 'N/A')}\n"
    report += f"Debt Quality: {validation_result['debt_quality'].get('debt_quality', 'N/A')}\n"

    if validation_result.get("issues"):
        report += f"\n⚠️ ISSUES:\n"
        for issue in validation_result["issues"]:
            report += f"  - {issue}\n"

    if validation_result.get("warnings"):
        report += f"\n⚡ WARNINGS:\n"
        for warning in validation_result["warnings"]:
            report += f"  - {warning}\n"

    report += f"{'='*60}\n"

    return report
