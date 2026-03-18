import json
import os
from datetime import datetime

MEMORY_FILE = "memory.json"

def save_analysis(tickers, analysis, historical):
    memory = load_memory()
    
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "analysis": analysis,
        "indicators": {}
    }
    
    for ticker in tickers:
        if ticker in historical and historical[ticker]:
            entry["indicators"][ticker] = {
                "rsi": historical[ticker].get("rsi"),
                "rsi_signal": historical[ticker].get("rsi_signal"),
                "ma_signal": historical[ticker].get("ma_signal"),
                "trend": historical[ticker].get("trend"),
                "volume_signal": historical[ticker].get("volume_signal")
            }
    
    memory.append(entry)
    
    if len(memory) > 50:
        memory = memory[-50:]
    
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def get_memory_summary():
    memory = load_memory()
    
    if not memory:
        return "No previous sessions recorded yet."
    
    last_5 = memory[-5:]
    
    summary = f"Last {len(last_5)} sessions:\n"
    
    for entry in last_5:
        summary += f"\n{entry['timestamp']}:\n"
        for ticker, indicators in entry.get("indicators", {}).items():
            rsi = indicators.get('rsi')
            trend = indicators.get('trend')
            if rsi and trend:
                summary += f"  {ticker}: RSI {rsi} ({indicators.get('rsi_signal')}), {trend}\n"
    
    lines = summary.split("\n")
    if len(lines) > 60:
        summary = "\n".join(lines[:60]) + "\n[Earlier sessions truncated]"
    
    return summary