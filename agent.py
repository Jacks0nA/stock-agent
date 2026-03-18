import anthropic
import os
import time
import streamlit as st
from dotenv import load_dotenv
from memory import save_analysis, get_memory_summary
from earnings import get_earnings_summary
from sectors import get_market_summary

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

HIGH_ACCURACY_ASSETS = {
    "SPY": 63.8, "DOGE-USD": 63.6, "WEAT": 63.5, "MDB": 63.0,
    "V": 61.7, "BMY": 61.0, "SYK": 60.8, "HAL": 60.7,
    "SCHW": 60.0, "MS": 59.7, "ZM": 59.5, "OVV": 67.9,
    "JPM": 66.7, "VLO": 77.8, "PSX": 75.0, "GD": 76.9,
    "ZW=F": 75.0, "PFE": 72.7, "AMD": 66.7, "VRTX": 66.7
}

LOW_ACCURACY_ASSETS = {
    "FANG": 44.3, "AMZN": 43.6, "UNH": 43.5, "C": 43.3,
    "TMO": 42.9, "GC=F": 42.2, "RF": 42.1, "DVN": 41.2,
    "RTX": 40.0, "CPER": 36.7
}

def get_accuracy_context(tickers):
    context = "\nHistorical signal accuracy for assets in this session:\n"
    high = [t for t in tickers if t in HIGH_ACCURACY_ASSETS]
    low = [t for t in tickers if t in LOW_ACCURACY_ASSETS]
    if high:
        context += "HIGH CONFIDENCE (trust these signals more):\n"
        for t in high:
            context += f"  {t}: {HIGH_ACCURACY_ASSETS[t]}% historical accuracy\n"
    if low:
        context += "LOW CONFIDENCE (treat with extra caution):\n"
        for t in low:
            context += f"  {t}: {LOW_ACCURACY_ASSETS[t]}% historical accuracy\n"
    return context

def analyse_stocks(df, news, historical, earnings, market_context, insider_summary=None, options_summary=None):
    data_string = df.to_string(index=False)
    tickers = df["ticker"].tolist()

    news_string = ""
    for ticker, data in news.items():
        news_string += f"\n{ticker} — Overall sentiment: {data['overall_sentiment']} (score: {data['avg_score']})\n"
        for h in data["headlines"]:
            news_string += f"  {h['sentiment']} ({h['score']}) — {h['title']}\n"

    historical_string = ""
    for ticker, data in historical.items():
        if data:
            historical_string += f"\n{ticker}:\n"
            historical_string += f"  30d High: {data.get('high_30d', 'N/A')}  Low: {data.get('low_30d', 'N/A')}  Avg: {data.get('avg_30d', 'N/A')}\n"
            historical_string += f"  Overall trend: {data.get('trend', 'N/A')}\n"
            historical_string += f"  MA20: {data.get('ma20', 'N/A')}  MA50: {data.get('ma50', 'N/A')}\n"
            historical_string += f"  MA Signal: {data.get('ma_signal', 'N/A')}\n"
            historical_string += f"  RSI: {data.get('rsi', 'N/A')} — {data.get('rsi_signal', 'N/A')}\n"
            historical_string += f"  Volume: {data.get('volume_signal', 'N/A')}\n"

    insider_string = "No significant insider buying detected."
    if insider_summary:
        insider_string = "INSIDER BUYING ACTIVITY:\n"
        for ticker, data in insider_summary.items():
            insider_string += f"\n{ticker} — {data['signal']}\n"
            insider_string += f"  Total: ${data['total_value']:,.0f} across {data['num_trades']} trades\n"
            for trade in data["trades"][:2]:
                insider_string += f"  {trade['date']} — {trade['insider']} ({trade['title']}) bought {trade['shares']:,.0f} shares @ ${trade['price']:.2f}\n"

    options_string = "No unusual options activity detected."
    if options_summary:
        options_string = "UNUSUAL OPTIONS FLOW:\n"
        for ticker, data in options_summary.items():
            options_string += f"\n{ticker} — {data['overall']}\n"
            options_string += f"  Call value: ${data['call_value']:,.0f}  Put value: ${data['put_value']:,.0f}\n"
            for flow in data["flow"][:2]:
                options_string += f"  {flow['signal']} {flow['type']} — Strike ${flow['strike']} exp {flow['expiry']} — Vol {flow['volume']:,} — ${flow['total_value']:,.0f}\n"

    memory_summary = get_memory_summary()
    earnings_summary = get_earnings_summary(earnings)
    market_summary = get_market_summary(market_context)
    accuracy_context = get_accuracy_context(tickers)

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": f"""You are a professional stock market analyst with memory of previous sessions and access to institutional flow data.

Previous session memory:
{memory_summary}

Market and sector context:
{market_summary}

Historical signal accuracy:
{accuracy_context}

Live price data:
{data_string}

Technical indicators and 30 day history:
{historical_string}

Latest news with sentiment scores:
{news_string}

Insider buying activity (SEC Form 4 — genuine cash purchases only):
{insider_string}

Unusual options flow (institutional money):
{options_string}

Upcoming earnings:
{earnings_summary}

Please analyse and provide:
1. Market context — broad move or stock specific?
2. Sector correlation — are moves explained by sector ETFs?
3. RSI analysis — flag overbought or oversold stocks
4. Moving average signals — above or below MA20 and MA50?
5. Volume analysis — are moves backed by volume?
6. Options flow — what is institutional money betting on?
7. Insider activity — any meaningful cash purchases?
8. Sentiment analysis — positive or negative news?
9. Earnings warnings — any stocks reporting in 7 days?
10. Comparison to previous sessions — what has changed?

Then give me:
🟢 BUY signals — strength not explained by broad market
🔴 AVOID signals — weakness or bearish technicals
⚪ WATCH signals — needs confirmation

For every BUY signal:
- Why: biggest reason to buy
- Position type: LONG or SHORT
- Hold time: Scalp / Swing / Position / Investor
- Entry: ideal price
- Target: realistic price target
- Stop loss: where to cut
- Risk/reward ratio
- Options flow confirms or contradicts?
- Insider buying present?
- Confidence: Low / Medium / High

For every AVOID signal:
- Why and what would change your mind

For every WATCH signal:
- Specific trigger before entering

One line prediction per stock: direction, confidence, biggest reason.

IMPORTANT: Weight confidence by historical accuracy. Flag when options flow contradicts technical signals — that divergence is the most important thing to highlight. Be direct. Make a call."""
                    }
                ]
            )

            analysis_text = message.content[0].text
            save_analysis(tickers, analysis_text, historical)
            return analysis_text

        except anthropic.APIStatusError as e:
            if attempt < 2:
                st.warning(f"Claude is busy, retrying in 10 seconds... (attempt {attempt + 1}/3)")
                time.sleep(10)
            else:
                return "Claude is currently overloaded. Please wait a moment and refresh."