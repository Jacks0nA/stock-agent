"""
Tracks Deep Dive verdicts in Supabase, checks outcomes at 5 and 10 days,
and feeds a compact accuracy summary back into Claude's prompts.

Requires a 'predictions' table in Supabase — create it once with:

    CREATE TABLE predictions (
        id BIGSERIAL PRIMARY KEY,
        ticker TEXT NOT NULL,
        verdict TEXT NOT NULL,
        entry_price FLOAT,
        confidence TEXT,
        source TEXT DEFAULT 'deep_dive',
        created_at TEXT,
        price_5d FLOAT,
        pct_5d FLOAT,
        correct_5d BOOLEAN,
        price_10d FLOAT,
        pct_10d FLOAT,
        correct_10d BOOLEAN
    );
"""

import os
import httpx
import yfinance as yf
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

GMT = timezone.utc


def _headers():
    return {
        "apikey": os.getenv("SUPABASE_KEY"),
        "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}",
        "Content-Type": "application/json",
    }


def _base():
    return os.getenv("SUPABASE_URL")


def save_prediction(ticker, verdict, entry_price, confidence, source="deep_dive"):
    """Save a new verdict to Supabase after a Deep Dive run."""
    if verdict not in ("BUY", "AVOID"):
        return  # WATCH doesn't have a clear right/wrong — don't track
    try:
        httpx.post(
            f"{_base()}/rest/v1/predictions",
            headers=_headers(),
            json={
                "ticker": ticker,
                "verdict": verdict,
                "entry_price": float(entry_price) if entry_price else None,
                "confidence": confidence,
                "source": source,
                "created_at": datetime.now(GMT).strftime("%Y-%m-%d %H:%M"),
            },
        )
    except Exception as e:
        print(f"save_prediction error: {e}")


def check_prediction_outcomes():
    """
    For any prediction that is 5+ or 10+ days old and not yet checked,
    fetch the current price and mark whether the call was correct.
    Call this once per app session — it's silent (no UI).
    """
    try:
        resp = httpx.get(
            f"{_base()}/rest/v1/predictions?select=*&order=created_at.desc",
            headers=_headers(),
        )
        predictions = resp.json() or []
    except Exception as e:
        print(f"check_prediction_outcomes fetch error: {e}")
        return

    now = datetime.now(GMT)

    for p in predictions:
        try:
            created = datetime.strptime(p["created_at"], "%Y-%m-%d %H:%M").replace(tzinfo=GMT)
            days_old = (now - created).days
            entry = float(p["entry_price"]) if p["entry_price"] else None
            if not entry:
                continue

            updates = {}

            if days_old >= 5 and p.get("price_5d") is None:
                hist = yf.Ticker(p["ticker"]).history(period="1d")
                if len(hist) > 0:
                    current = float(hist["Close"].iloc[-1])
                    pct = round(((current - entry) / entry) * 100, 2)
                    correct = (p["verdict"] == "BUY" and pct > 0) or (p["verdict"] == "AVOID" and pct < 0)
                    updates.update({"price_5d": current, "pct_5d": pct, "correct_5d": correct})

            if days_old >= 10 and p.get("price_10d") is None:
                hist = yf.Ticker(p["ticker"]).history(period="1d")
                if len(hist) > 0:
                    current = float(hist["Close"].iloc[-1])
                    pct = round(((current - entry) / entry) * 100, 2)
                    correct = (p["verdict"] == "BUY" and pct > 0) or (p["verdict"] == "AVOID" and pct < 0)
                    updates.update({"price_10d": current, "pct_10d": pct, "correct_10d": correct})

            if updates:
                httpx.patch(
                    f"{_base()}/rest/v1/predictions?id=eq.{p['id']}",
                    headers=_headers(),
                    json=updates,
                )

        except Exception as e:
            print(f"check_prediction_outcomes row error ({p.get('ticker')}): {e}")


def get_accuracy_summary():
    """
    Returns a compact accuracy string for Claude's prompt.
    ~80-120 tokens — negligible cost.
    """
    try:
        resp = httpx.get(
            f"{_base()}/rest/v1/predictions?select=*&order=created_at.desc&limit=50",
            headers=_headers(),
        )
        predictions = resp.json() or []
    except Exception:
        return "No prediction history available."

    if not predictions:
        return "No prediction history yet — this is an early run."

    checked = [p for p in predictions if p.get("correct_5d") is not None]
    if not checked:
        pending = len(predictions)
        return f"Predictions logged: {pending} — all pending 5-day outcome check."

    buy_calls = [p for p in checked if p["verdict"] == "BUY"]
    avoid_calls = [p for p in checked if p["verdict"] == "AVOID"]

    def rate(calls):
        if not calls:
            return None, 0
        correct = sum(1 for p in calls if p["correct_5d"])
        return round(correct / len(calls) * 100), len(calls)

    buy_rate, buy_n = rate(buy_calls)
    avoid_rate, avoid_n = rate(avoid_calls)

    lines = ["PAST PREDICTION ACCURACY (5-day outcomes):"]
    if buy_rate is not None:
        lines.append(f"BUY calls: {buy_rate}% correct ({buy_n} tracked)")
    if avoid_rate is not None:
        lines.append(f"AVOID calls: {avoid_rate}% correct ({avoid_n} tracked)")

    # Flag recent misses so Claude can learn from them
    recent_wrong = [
        p for p in checked[-20:]
        if not p["correct_5d"] and p.get("pct_5d") is not None
    ]
    if recent_wrong:
        misses = ", ".join(
            f"{p['ticker']}({p['verdict']}→{p['pct_5d']:+.1f}%)"
            for p in recent_wrong[-4:]
        )
        lines.append(f"Recent misses: {misses}")

    # Flag recent wins for calibration
    recent_right = [
        p for p in checked[-20:]
        if p["correct_5d"] and p.get("pct_5d") is not None
    ]
    if recent_right:
        wins = ", ".join(
            f"{p['ticker']}({p['verdict']}→{p['pct_5d']:+.1f}%)"
            for p in recent_right[-4:]
        )
        lines.append(f"Recent wins: {wins}")

    return "\n".join(lines)
