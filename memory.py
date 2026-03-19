import os
import json
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def get_headers():
    return {
        "apikey": os.getenv("SUPABASE_KEY"),
        "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}",
        "Content-Type": "application/json"
    }

def get_base_url():
    return os.getenv("SUPABASE_URL")

def save_analysis(tickers, analysis, historical):
    try:
        indicators = {}
        for ticker in tickers:
            if ticker in historical and historical[ticker]:
                indicators[ticker] = {
                    "rsi": historical[ticker].get("rsi"),
                    "rsi_signal": historical[ticker].get("rsi_signal"),
                    "ma_signal": historical[ticker].get("ma_signal"),
                    "trend": historical[ticker].get("trend"),
                    "volume_signal": historical[ticker].get("volume_signal")
                }

        url = f"{get_base_url()}/rest/v1/memory"
        httpx.post(url, headers=get_headers(), json={
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "analysis": analysis,
            "indicators": indicators
        })

        # Keep only last 50 — delete oldest if over limit
        all_rows = httpx.get(
            f"{get_base_url()}/rest/v1/memory?select=id&order=id.asc",
            headers=get_headers()
        ).json()

        if len(all_rows) > 50:
            oldest_ids = [r["id"] for r in all_rows[:-50]]
            for oid in oldest_ids:
                httpx.delete(
                    f"{get_base_url()}/rest/v1/memory?id=eq.{oid}",
                    headers=get_headers()
                )

    except Exception as e:
        print(f"Memory save error: {e}")

def load_memory():
    try:
        url = f"{get_base_url()}/rest/v1/memory?select=*&order=id.asc"
        response = httpx.get(url, headers=get_headers())
        return response.json()
    except Exception as e:
        print(f"Memory load error: {e}")
        return []

def get_memory_summary():
    memory = load_memory()

    if not memory:
        return "No previous sessions recorded yet."

    last_5 = memory[-5:]
    summary = f"Last {len(last_5)} sessions:\n"

    for entry in last_5:
        summary += f"\n{entry['timestamp']}:\n"
        for ticker, indicators in entry.get("indicators", {}).items():
            rsi = indicators.get("rsi")
            trend = indicators.get("trend")
            if rsi and trend:
                summary += f"  {ticker}: RSI {rsi} ({indicators.get('rsi_signal')}), {trend}\n"

    lines = summary.split("\n")
    if len(lines) > 60:
        summary = "\n".join(lines[:60]) + "\n[Earlier sessions truncated]"

    return summary