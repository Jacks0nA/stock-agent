import os
import json
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def get_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return create_client(url, key)

def save_analysis(tickers, analysis, historical):
    try:
        client = get_client()

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

        client.table("memory").insert({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "analysis": analysis,
            "indicators": indicators
        }).execute()

        # Keep only last 50 entries — delete older ones
        all_rows = client.table("memory").select("id").order("id", desc=False).execute()
        if len(all_rows.data) > 50:
            oldest_ids = [r["id"] for r in all_rows.data[:-50]]
            client.table("memory").delete().in_("id", oldest_ids).execute()

    except Exception as e:
        print(f"Memory save error: {e}")

def load_memory():
    try:
        client = get_client()
        result = client.table("memory").select("*").order("id", desc=False).execute()
        return result.data or []
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