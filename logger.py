import os
from datetime import datetime

LOGS_DIR = "logs"

def ensure_logs_dir():
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)

def save_daily_log(analysis_text, mode="Daily", tickers=None):
    ensure_logs_dir()
    today = datetime.now().strftime("%Y-%m-%d")
    time_now = datetime.now().strftime("%H:%M")
    filename = f"{LOGS_DIR}/analysis_{today}.txt"
    
    lines = extract_key_points(analysis_text)
    
    with open(filename, "a") as f:
        f.write(f"\n{'='*50}\n")
        f.write(f"{mode.upper()} ANALYSIS — {today} {time_now} GMT\n")
        if tickers:
            f.write(f"Assets: {', '.join(tickers)}\n")
        f.write(f"{'='*50}\n\n")
        f.write(lines)
        f.write("\n")
    
    return filename

def extract_key_points(analysis_text):
    lines = analysis_text.split("\n")
    output = []
    
    capture_sections = [
        "BUY", "AVOID", "WATCH",
        "🟢", "🔴", "⚪",
        "market context", "market:",
        "prediction", "confidence",
        "entry:", "target:", "stop",
        "risk/reward", "r:r",
        "hold time", "position type"
    ]
    
    skip_sections = [
        "rsi analysis", "moving average",
        "volume analysis", "sector correlation",
        "technical indicator"
    ]
    
    capturing = False
    
    for line in lines:
        line_lower = line.lower().strip()
        
        if not line.strip():
            if capturing:
                output.append("")
            continue
        
        if any(skip in line_lower for skip in skip_sections):
            capturing = False
            continue
        
        if any(section in line_lower for section in capture_sections):
            capturing = True
        
        if capturing and line.strip():
            cleaned = line.strip()
            if len(cleaned) > 2:
                output.append(cleaned)
    
    if not output:
        output = [l.strip() for l in lines if l.strip()][:40]
    
    return "\n".join(output)

def get_todays_log():
    ensure_logs_dir()
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{LOGS_DIR}/analysis_{today}.txt"
    
    if not os.path.exists(filename):
        return "No analyses run today yet."
    
    with open(filename, "r") as f:
        return f.read()

def list_recent_logs():
    ensure_logs_dir()
    files = sorted([f for f in os.listdir(LOGS_DIR) if f.endswith(".txt")], reverse=True)
    return files[:7]