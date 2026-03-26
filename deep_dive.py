import anthropic
import os
import time
import streamlit as st
from dotenv import load_dotenv
from fetcher import fetch_stock_data, fetch_historical_data
from news import fetch_stock_news
from options import get_options_summary
from insider import get_insider_summary
from earnings import get_earnings_calendar, get_earnings_summary
from sectors import get_market_context, get_market_summary

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _build_options_string(options_summary):
    if not options_summary:
        return "No significant options activity detected."
    result = ""
    for ticker, data in options_summary.items():
        result += f"{ticker} {data['overall']}: calls ${data['call_value']:,.0f} puts ${data['put_value']:,.0f}\n"
        for flow in data["flow"][:3]:
            result += f"  {flow['signal']} {flow['type']} ${flow['strike']} exp {flow['expiry']} vol {flow['volume']:,} — ${flow['total_value']:,.0f}\n"
    return result


def run_deep_dive(ticker: str, use_enhanced_news: bool = False) -> str:
    ticker = ticker.strip().upper()

    with st.spinner(f"Fetching price data for {ticker}..."):
        df = fetch_stock_data([ticker])
        historical = fetch_historical_data([ticker])

    with st.spinner("Fetching market context..."):
        market_context = get_market_context()

    with st.spinner("Fetching news..."):
        if use_enhanced_news:
            from news_enhanced import fetch_stock_news_enhanced
            news = fetch_stock_news_enhanced([ticker])
        else:
            news = fetch_stock_news([ticker])

    with st.spinner("Fetching options flow..."):
        options_summary = get_options_summary([ticker])

    with st.spinner("Checking insider activity..."):
        insider_summary = get_insider_summary([ticker])

    with st.spinner("Checking earnings calendar..."):
        earnings = get_earnings_calendar([ticker])

    # Build context strings
    price_row = df[df["ticker"] == ticker]
    if not price_row.empty:
        row = price_row.iloc[0]
        price_string = (
            f"{ticker}: ${row['price']} | change {row['change']} ({row['change_%']}%) {row['direction']}"
        )
    else:
        price_string = f"{ticker}: price unavailable"

    hist = historical.get(ticker, {})
    if hist:
        technical_string = (
            f"RSI: {hist.get('rsi', 'N/A')} ({hist.get('rsi_signal', 'N/A')})\n"
            f"MA20: {hist.get('ma20', 'N/A')} | MA50: {hist.get('ma50', 'N/A')}\n"
            f"Signal: {hist.get('ma_signal', 'N/A')}\n"
            f"Trend: {hist.get('trend', 'N/A')}\n"
            f"Volume: {hist.get('volume_signal', 'N/A')}\n"
            f"30d High: {hist.get('high_30d', 'N/A')} | 30d Low: {hist.get('low_30d', 'N/A')} | 30d Avg: {hist.get('avg_30d', 'N/A')}"
        )
    else:
        technical_string = "Technical data unavailable."

    ticker_news = news.get(ticker, {})
    headlines = ticker_news.get("headlines", [])
    news_string = f"Sentiment: {ticker_news.get('overall_sentiment', 'N/A')} (score {ticker_news.get('avg_score', 0)})\n"
    for h in headlines[:5]:
        age = h.get("age_str", "")
        source = h.get("source", "")
        summary = h.get("summary", "")
        news_string += f"  {h['sentiment']} ({h['score']}) [{age} — {source}]: {h['title'][:120]}\n"
        if summary:
            news_string += f"    {summary[:250]}\n"

    options_string = _build_options_string(options_summary)

    insider_string = "No insider activity detected."
    if insider_summary and ticker in insider_summary:
        d = insider_summary[ticker]
        insider_string = f"{d['signal']} — ${d['total_value']:,.0f} total"

    earnings_summary = get_earnings_summary(earnings)
    market_summary = get_market_summary(market_context)

    with st.spinner(f"Claude running deep dive on {ticker}..."):
        for attempt in range(3):
            try:
                message = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4000,
                    messages=[
                        {
                            "role": "user",
                            "content": f"""You are a professional equity analyst. Produce a comprehensive deep-dive investment thesis for a single stock.

STOCK: {ticker}

MARKET CONTEXT:
{market_summary}

PRICE & TECHNICALS:
{price_string}
{technical_string}

NEWS & SENTIMENT:
{news_string}

OPTIONS FLOW:
{options_string}

INSIDER ACTIVITY:
{insider_string}

EARNINGS:
{earnings_summary}

---

Produce a full investment thesis in the following format:

## {ticker} — Deep Dive Analysis

### 1. Snapshot
One paragraph: what this company does, sector, market cap tier, why it matters right now.

### 2. Technical Picture
Detailed breakdown of RSI, moving averages, trend, volume, support/resistance levels, and any notable chart patterns. State clearly whether the technicals are bullish, bearish, or neutral.

### 3. News & Sentiment
Summarise the key stories driving sentiment. Are they short-term noise or structural? How does sentiment compare to price action?

### 4. Options Flow
Interpret the options activity. Are smart money bets skewed bullish or bearish? What do the strike prices and expiries imply about expected moves?

### 5. Insider Activity
What are insiders doing and what does it signal? If no activity, state that and note whether absence is significant.

### 6. Earnings Risk
When is the next earnings date? Is the stock cheap or expensive into earnings? What are the key metrics to watch?

### 7. Macro & Sector Tailwinds / Headwinds
How does the current macro environment affect this stock? Any sector-specific risks or catalysts?

### 8. Bull Case
Three concrete reasons to BUY with specific price targets and catalysts.

### 9. Bear Case
Three concrete reasons to AVOID with specific downside levels and risks.

### 10. Investment Thesis

**VERDICT: [BUY / WATCH / AVOID]**

**Entry Price:** $[price or range]
**Target Price:** $[price] ([upside %])
**Stop Loss:** $[price] ([downside %])
**Risk/Reward:** [ratio]
**Confidence Level:** [LOW / MEDIUM / CONFIDENT / SUPER]
**Time Horizon:** [days/weeks]

Final paragraph: 3-5 sentences synthesising the bull and bear cases into your overall conclusion. Be direct and specific. Do not hedge excessively."""
                        }
                    ]
                )
                return message.content[0].text

            except anthropic.APIStatusError:
                if attempt < 2:
                    st.warning(f"Claude is busy, retrying... (attempt {attempt + 1}/3)")
                    time.sleep(10)
                else:
                    return "Claude is currently overloaded. Please wait a moment and try again."
