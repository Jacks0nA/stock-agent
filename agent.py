import anthropic
import os
import time
import json
import streamlit as st
from dotenv import load_dotenv
from memory import save_analysis, get_memory_summary
from earnings import get_earnings_summary
from sectors import get_market_summary
from portfolio import (
    get_portfolio_summary, get_open_positions, get_current_prices,
    open_position, close_position, update_position,
    check_stop_losses, check_max_hold, get_portfolio_balance,
    MAX_POSITIONS, CONFIDENCE_SIZES
)

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

HIGH_ACCURACY_ASSETS = {
    "SNAP": 80.0,
    "HAL": 80.0,
    "XRP-USD": 71.4,
    "FANG": 66.7,
    "DOCU": 60.0,
    "SOL-USD": 60.0,
}

LOW_ACCURACY_ASSETS = {
    "XLY": 0.0,
    "ZW=F": 0.0,
    "RBLX": 5.0,
    "QQQ": 6.7,
    "NVDA": 10.5,
    "C": 12.5,
    "BTC-USD": 12.5,
    "RF": 14.3,
    "RTX": 14.3,
    "XLK": 14.3,
    "PH": 18.2,
    "META": 20.0,
    "MSFT": 20.0,
    "XLI": 20.0,
    "GE": 21.4,
    "XLU": 22.2,
    "EEM": 25.0,
    "AMD": 25.0,
    "GC=F": 25.0,
    "ZM": 25.0,
    "NFLX": 25.0,
    "BK": 25.0,
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

def determine_confidence_level(ticker, score, historical, options_summary, insider_summary):
    """
    Determines confidence tier based on score, confirmers, insider and options data.
    Returns LOW, MEDIUM, CONFIDENT, or SUPER.
    """
    strong_confirmers = 0
    has_insider = ticker in insider_summary if insider_summary else False
    has_options = ticker in options_summary if options_summary else False

    if historical.get(ticker):
        rsi = historical[ticker].get("rsi")
        if rsi and rsi < 35:
            strong_confirmers += 1

    if score >= 14 and strong_confirmers >= 2 and has_insider and has_options:
        return "SUPER"
    elif score >= 11 and strong_confirmers >= 1 and (has_insider or has_options):
        return "CONFIDENT"
    elif score >= 9 and (has_insider or has_options):
        return "MEDIUM"
    else:
        return "LOW"

def review_open_positions(current_prices, news, options_summary, market_context):
    """
    Reviews all open positions and returns Claude's decisions on each.
    """
    open_positions = get_open_positions()
    if not open_positions:
        return "", []

    position_reviews = ""
    for p in open_positions:
        ticker = p["ticker"]
        current = current_prices.get(ticker, float(p["entry_price"]))
        entry = float(p["entry_price"])
        pnl_pct = round(((current - entry) / entry) * 100, 2)
        days_held = (
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc) -
            __import__("datetime").datetime.strptime(p["opened_at"], "%Y-%m-%d %H:%M").replace(
                tzinfo=__import__("datetime").timezone.utc)
        ).days

        ticker_news = news.get(ticker, {})
        news_summary = ticker_news.get("overall_sentiment", "No news")

        position_reviews += f"""
{ticker}: entry {entry} | current {current} | pnl {pnl_pct}% | target {p['target_price']} | stop {p['stop_loss']} | day {days_held}/{10} | confidence {p['confidence']}
News: {news_summary}
Original reasoning: {p['claude_reasoning'][:200] if p['claude_reasoning'] else 'N/A'}
"""

    return position_reviews, open_positions

def analyse_stocks(df, news, historical, earnings, market_context,
                   insider_summary=None, options_summary=None, market_is_open=True):

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
    portfolio_summary = get_portfolio_summary()

    # Check stop losses and max hold before analysis
    open_positions = get_open_positions()
    if open_positions:
        position_tickers = [p["ticker"] for p in open_positions]
        all_tickers = list(set(tickers + position_tickers))
        current_prices = get_current_prices(all_tickers)
        check_stop_losses(open_positions, current_prices)
        check_max_hold(open_positions, current_prices)
        # Refresh after auto-closures
        open_positions = get_open_positions()
    else:
        current_prices = get_current_prices(tickers)

    # Get position reviews for Claude
    position_reviews, open_positions = review_open_positions(
        current_prices, news, options_summary, market_context
    )

    available_slots = MAX_POSITIONS - len(open_positions)
    balance = get_portfolio_balance()

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2500,
                messages=[
                    {
                        "role": "user",
                        "content": f"""You are a professional stock analyst managing a paper trading portfolio.

MARKET: {market_summary}

PORTFOLIO: {portfolio_summary}

OPEN POSITION REVIEW:
{position_reviews if position_reviews else "No open positions to review."}

ACCURACY: {accuracy_context}

MEMORY: {memory_summary}

PRICES & TECHNICALS:
{data_string}
{historical_string}

NEWS: {news_string}

OPTIONS: {options_string}

INSIDER: {insider_string}

EARNINGS: {earnings_summary}

INSTRUCTIONS:

PART 1 — REVIEW OPEN POSITIONS:
For each open position review whether to HOLD or EXIT.
Rules you must follow:
- Stop loss NEVER moves down
- When target is hit, move stop loss up to just below target achieved
- Exit if confidence drops to LOW
- Exit if stop loss breached (already handled automatically)
- Maximum 10 days hold (already handled automatically)

For each open position output:
POSITION_REVIEW: [TICKER] | [HOLD/EXIT] | [NEW_TARGET if changed] | [NEW_STOP if changed] | [NEW_CONFIDENCE] | [REASONING]

PART 2 — NEW TRADE DECISIONS:
Available portfolio slots: {available_slots}
Available cash: £{round(balance, 2)}

Confidence tiers and position sizes:
- SUPER (£2000): score 14+, all three strong confirmers, both insider AND options flow, high accuracy asset
- CONFIDENT (£1000): score 11-13, two strong confirmers, insider OR options flow, high accuracy asset
- MEDIUM (£250): score 9-10, one strong confirmer, insider OR options
- LOW (£100): score 7-8, one confirmer, no insider/options

Only open a position if you genuinely believe in the setup.
It is always better to say NO TRADE than to force a low quality setup.

For each new trade output:
NEW_TRADE: [TICKER] | [LONG/SHORT] | [ENTRY_PRICE] | [TARGET] | [STOP_LOSS] | [CONFIDENCE] | [REASONING]

If no good setups: NO_TRADE: [REASONING]

PART 3 — ANALYSIS:
Provide your standard market analysis, key signals, and one-line summary table.

Weight confidence by historical accuracy. Flag options/technical divergences prominently.
Optimal hold period is 5 days. BUY signals have 91.2% historical accuracy in bull markets."""
                    }
                ]
            )

            analysis_text = message.content[0].text

            # Parse and execute trade decisions
            execute_trade_decisions(
                analysis_text, historical, options_summary,
                insider_summary, current_prices, open_positions,
                market_is_open=market_is_open
            )

            save_analysis(tickers, analysis_text, historical)
            return analysis_text

        except anthropic.APIStatusError as e:
            if attempt < 2:
                st.warning(f"Claude is busy, retrying in 10 seconds... (attempt {attempt + 1}/3)")
                time.sleep(10)
            else:
                return "Claude is currently overloaded. Please wait a moment and refresh."

def execute_trade_decisions(analysis_text, historical, options_summary,
                             insider_summary, current_prices, open_positions,
                             market_is_open=True):
    """
    Parses Claude's structured output and executes position opens/updates/closes.
    """
    lines = analysis_text.split("\n")

    open_position_map = {p["ticker"]: p for p in open_positions}

    for line in lines:
        line = line.strip()

        # Handle position reviews
        if line.startswith("POSITION_REVIEW:"):
            try:
                parts = line.replace("POSITION_REVIEW:", "").strip().split("|")
                ticker = parts[0].strip()
                action = parts[1].strip()
                new_target = parts[2].strip() if len(parts) > 2 else None
                new_stop = parts[3].strip() if len(parts) > 3 else None
                new_confidence = parts[4].strip() if len(parts) > 4 else None
                reasoning = parts[5].strip() if len(parts) > 5 else ""

                if ticker in open_position_map:
                    position = open_position_map[ticker]
                    current_price = current_prices.get(ticker, float(position["entry_price"]))

                    if action == "EXIT":
                        close_position(position["id"], current_price, reasoning)
                    else:
                        updates = {}
                        if new_target and new_target not in ["", "unchanged"]:
                            try:
                                updates["target_price"] = float(new_target)
                            except ValueError:
                                pass
                        if new_stop and new_stop not in ["", "unchanged"]:
                            try:
                                updates["stop_loss"] = float(new_stop)
                            except ValueError:
                                pass
                        if new_confidence and new_confidence not in ["", "unchanged"]:
                            updates["confidence"] = new_confidence
                        updates["current_price"] = current_price
                        if updates:
                            update_position(position["id"], updates)

            except Exception as e:
                print(f"Position review parse error: {e}")

        # Handle new trades
        elif line.startswith("NEW_TRADE:"):
            if not market_is_open:
                print(f"US market closed — new position not opened: {line}")
                continue
            try:
                parts = line.replace("NEW_TRADE:", "").strip().split("|")
                ticker = parts[0].strip()
                direction = parts[1].strip()
                entry_price = float(parts[2].strip())
                target = float(parts[3].strip())
                stop_loss = float(parts[4].strip())
                confidence = parts[5].strip()
                reasoning = parts[6].strip() if len(parts) > 6 else ""

                position_size = CONFIDENCE_SIZES.get(confidence, 100.0)
                balance = get_portfolio_balance()
                current_open = len(get_open_positions())

                if current_open >= MAX_POSITIONS:
                    print(f"Max positions reached — skipping {ticker}")
                    continue

                if position_size > balance:
                    print(f"Insufficient balance for {ticker} — skipping")
                    continue

                open_position(
                    ticker, direction, entry_price, target,
                    stop_loss, confidence, 0, reasoning, position_size
                )

            except Exception as e:
                print(f"New trade parse error: {e}")