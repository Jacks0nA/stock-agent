"""
Debate Framework: Bull vs Bear Agent Analysis

Two specialized agents analyze the same stock independently:
- Bull Case Agent: Argues why you should BUY
- Bear Case Agent: Argues why you should AVOID

Both present evidence. Final signal = consensus with confidence.
Reduces bad calls by forcing consideration of both sides.
"""

import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


class DebateAnalyzer:
    """Two-agent debate system for better trade decisions."""

    def __init__(self):
        self.model = "claude-3-5-sonnet-20241022"

    def get_bull_case(self, ticker, price, technical_signal, news_sentiment, recovery_prob, moat_score):
        """
        Bull Case Agent: Arguments FOR buying.

        Args:
            ticker: Stock ticker
            price: Current price
            technical_signal: BUY/WATCH/AVOID from technical analysis
            news_sentiment: Positive/Neutral/Negative
            recovery_prob: Monte Carlo recovery probability (0-1)
            moat_score: Competitive moat score (0-5)

        Returns:
            dict with bull case analysis
        """
        prompt = f"""You are a BULL CASE ANALYST. Your job is to make the strongest possible argument FOR buying {ticker} at ${price}.

EVIDENCE FOR BUYING:
- Technical Signal: {technical_signal}
- News Sentiment: {news_sentiment}
- Recovery Probability: {recovery_prob*100:.1f}%
- Competitive Moat: {moat_score}/5

Your task:
1. List 3-5 strongest reasons to BUY this stock
2. Focus on what's going RIGHT
3. Emphasize upside potential
4. Rate your confidence (0-100%)
5. What catalysts could drive this higher?

Format your response as:
BULL CASE FOR {ticker}
================
Reasons to Buy:
- [Reason 1]
- [Reason 2]
- [Reason 3]

Upside Potential: [expected return if thesis plays out]
Catalysts: [what could trigger a move]
Confidence: [0-100]%

Most Bullish Signal: [the #1 reason to buy]"""

        response = client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            "ticker": ticker,
            "case": "BULL",
            "analysis": response.content[0].text
        }

    def get_bear_case(self, ticker, price, technical_signal, news_sentiment, recovery_prob, moat_score):
        """
        Bear Case Agent: Arguments AGAINST buying (risks to consider).

        Args:
            ticker: Stock ticker
            price: Current price
            technical_signal: BUY/WATCH/AVOID from technical analysis
            news_sentiment: Positive/Neutral/Negative
            recovery_prob: Monte Carlo recovery probability (0-1)
            moat_score: Competitive moat score (0-5)

        Returns:
            dict with bear case analysis
        """
        prompt = f"""You are a BEAR CASE ANALYST. Your job is to make the strongest possible argument AGAINST buying {ticker} at ${price}.

EVIDENCE FOR CAUTION:
- Technical Signal: {technical_signal}
- News Sentiment: {news_sentiment}
- Recovery Probability: {recovery_prob*100:.1f}%
- Competitive Moat: {moat_score}/5

Your task:
1. List 3-5 biggest risks/reasons to AVOID this stock
2. Focus on what could go WRONG
3. Emphasize downside risks
4. Rate your confidence in the bear case (0-100%)
5. What could break your thesis?

Format your response as:
BEAR CASE FOR {ticker}
================
Reasons to Avoid:
- [Risk 1]
- [Risk 2]
- [Risk 3]

Downside Risk: [potential loss if thesis fails]
Breaking Points: [what would invalidate the bear case]
Confidence: [0-100]%

Most Bearish Signal: [the #1 reason to skip this]"""

        response = client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            "ticker": ticker,
            "case": "BEAR",
            "analysis": response.content[0].text
        }

    def get_risk_assessment(self, ticker, price, volatility, insider_activity):
        """
        Risk Officer Agent: Assessment of risk factors.

        Args:
            ticker: Stock ticker
            price: Current price
            volatility: Stock volatility (0-1)
            insider_activity: "BUY" / "SELL" / "None"

        Returns:
            dict with risk assessment
        """
        prompt = f"""You are a RISK OFFICER. Assess the risk level of {ticker} at ${price}.

RISK FACTORS:
- Volatility: {volatility*100:.1f}%
- Insider Activity: {insider_activity}

Your task:
1. Identify key risks (execution, market, company-specific)
2. Rate overall RISK LEVEL (LOW / MEDIUM / HIGH)
3. What's the worst-case scenario?
4. What position size makes sense? (1% / 2% / 3% of portfolio)
5. What would trigger a STOP LOSS?

Format your response as:
RISK ASSESSMENT FOR {ticker}
============================
Key Risks:
- [Risk 1]
- [Risk 2]

Overall Risk Level: [LOW/MEDIUM/HIGH]
Worst-Case Scenario: [stock drops X%]
Recommended Position Size: [X%]
Stop Loss Trigger: [price level or %]

Risk Mitigation: [how to protect yourself]"""

        response = client.messages.create(
            model=self.model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            "ticker": ticker,
            "case": "RISK",
            "analysis": response.content[0].text
        }

    def debate_stock(self, ticker, price, technical_signal, news_sentiment, recovery_prob, moat_score, volatility, insider_activity):
        """
        Full debate: Bull vs Bear vs Risk Officer.

        Returns:
            dict with all three perspectives + final recommendation
        """
        print(f"\n🎤 DEBATE FRAMEWORK: {ticker}")
        print("=" * 60)

        # Get all three perspectives
        print("  🟢 Bull Case Agent analyzing...")
        bull = self.get_bull_case(ticker, price, technical_signal, news_sentiment, recovery_prob, moat_score)

        print("  🔴 Bear Case Agent analyzing...")
        bear = self.get_bear_case(ticker, price, technical_signal, news_sentiment, recovery_prob, moat_score)

        print("  ⚠️ Risk Officer analyzing...")
        risk = self.get_risk_assessment(ticker, price, volatility, insider_activity)

        # Synthesize recommendation based on debate
        synthesis_prompt = f"""Based on three independent analyses, synthesize a final recommendation for {ticker}:

BULL CASE SUMMARY:
{bull['analysis'][:300]}...

BEAR CASE SUMMARY:
{bear['analysis'][:300]}...

RISK ASSESSMENT SUMMARY:
{risk['analysis'][:300]}...

FINAL DECISION:
Your task is to synthesize these three perspectives into a final recommendation:
1. Which side had stronger arguments? (Bull/Bear/Balanced)
2. What's the consensus risk level?
3. Final verdict: BUY / WATCH / AVOID
4. Confidence in this decision: 0-100%
5. Key condition: If [X happens], change decision to [Y]

Format:
DEBATE CONSENSUS FOR {ticker}
=============================
Stronger Case: [Bull/Bear/Balanced]
Risk Assessment: [LOW/MEDIUM/HIGH]

Final Verdict: [BUY/WATCH/AVOID]
Confidence: [0-100]%

Key Condition: If [condition], change to [new verdict]
Rationale: [1-2 sentences explaining the decision]"""

        synthesis = client.messages.create(
            model=self.model,
            max_tokens=400,
            messages=[{"role": "user", "content": synthesis_prompt}]
        )

        return {
            "ticker": ticker,
            "bull_case": bull["analysis"],
            "bear_case": bear["analysis"],
            "risk_assessment": risk["analysis"],
            "synthesis": synthesis.content[0].text,
            "debate_complete": True
        }


# Convenience function
def debate_stock(ticker, price, technical_signal, news_sentiment, recovery_prob, moat_score, volatility, insider_activity):
    """
    Quick function to run full debate on a stock.

    Returns:
        dict with debate results
    """
    analyzer = DebateAnalyzer()
    return analyzer.debate_stock(
        ticker, price, technical_signal, news_sentiment,
        recovery_prob, moat_score, volatility, insider_activity
    )


def format_debate_summary(debate_result):
    """
    Formats debate results into readable text.

    Args:
        debate_result: Dict from debate_stock()

    Returns:
        Formatted string summary
    """
    ticker = debate_result.get("ticker", "UNKNOWN")
    synthesis = debate_result.get("synthesis", "")

    summary = f"\n{'='*60}\n"
    summary += f"DEBATE VERDICT: {ticker}\n"
    summary += f"{'='*60}\n"
    summary += f"{synthesis}\n"
    summary += f"{'='*60}\n"

    return summary
