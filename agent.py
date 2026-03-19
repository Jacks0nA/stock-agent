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
    high = [f"{t}: {HIGH_ACCURACY_ASSETS[t]}%" for t in tickers if t in HIGH_ACCURACY_ASSETS]
    low = [f"{t}: {LOW_ACCURACY_ASSETS[t]}%" for t in tickers if t in LOW_ACCURACY_ASSETS]
    context = ""
    if high:
        context += f"HIGH CONFIDENCE: {', '.join(high)}\n"
    if low:
        context += f"LOW CONFIDENCE: {', '.join(low)}\n"
    return context if context else "No historical accuracy data for these assets.\n"

def build_news_string(news, max_per_stock=2):
    news_string = ""
    for ticker, data in news.items():
        if not data.get("has_signal") and data.get("avg_score", 0) == 0:
            news_string += f"{ticker}: No significant news\n"
            continue
        news_string += f"{ticker} ({data['overall_sentiment']} {data['avg_score']}):\n"
        significant = [h for h in data["headlines"] if abs(h["score"]) > 0.1]
        if not significant:
            significant = data["headlines"][:1]
        for h in significant[:max_per_stock]:
            news_string += f"  {h['sentiment']} ({h['score']}): {h['title'][:100]}\n"
    return news_string

def build_options_string(options_summary):
    if not options_summary:
        return "No significant options activity.\n"
    result = ""
    for ticker, data in options_summary.items():
        result += f"{ticker} {data['overall']}: calls ${data['call_value']:,.0f} puts ${data['put_value']:,.0f}\n"
        for flow in data["flow"][:2]:
            result += f"  {flow['signal']} {flow['type']} ${flow['strike']} exp {flow['expiry']} vol {flow['volume']:,}\n"
    return result

def analyse_stocks(df, news, historical, earnings, market_context, insider_summary=None, options_summary=None):
    data_string = df.to_string(index=False)
    tickers = df["ticker"].tolist()

    historical_string = ""
    for ticker, data in historical.items():
        if data:
            historical_string += f"{ticker}: RSI {data.get('rsi','N/A')} ({data.get('rsi_signal','N/A')}) | {data.get('ma_signal','N/A')} | {data.get('trend','N/A')} | Vol {data.get('volume_signal','N/A')}\n"

    insider_string = "None detected.\n"
    if insider_summary:
        insider_string = ""
        for ticker, data in insider_summary.items():
            insider_string += f"{ticker}: {data['signal']} — ${data['total_value']:,.0f} total\n"

    memory_summary = get_memory_summary()
    earnings_summary = get_earnings_summary(earnings)
    market_summary = get_market_summary(market_context)
    accuracy_context = get_accuracy_context(tickers)
    news_string = build_news_string(news)
    options_string = build_options_string(options_summary)

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2500,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Professional stock analyst. Be concise and direct.

MARKET: {market_summary}

ACCURACY: {accuracy_context}

MEMORY: {memory_summary}

PRICES & TECHNICALS:
{data_string}
{historical_string}

NEWS: {news_string}

OPTIONS: {options_string}

INSIDER: {insider_string}

EARNINGS: {earnings_summary}

Provide:
1. Market context (2 lines max)
2. Key RSI/MA signals (flagged only)
3. Options flow vs price divergences
4. Session comparison (what changed)

Then:
🟢 BUY: ticker, why, LONG/SHORT, hold time, entry, target, stop, R:R, confidence
🔴 AVOID: only flag if options flow or insider data strongly confirms bearish case — not from technicals alone
⚪ WATCH: ticker, specific trigger

One line per stock: direction | confidence | reason

Weight confidence by historical accuracy. Flag options/technical divergences prominently."""
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