import os
import json
from datetime import datetime

LOGS_DIR = "logs"
LOGS_INDEX = "logs/index.json"

def ensure_logs_dir():
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)

def load_index():
    ensure_logs_dir()
    if not os.path.exists(LOGS_INDEX):
        return {}
    with open(LOGS_INDEX, "r") as f:
        return json.load(f)

def save_index(index):
    with open(LOGS_INDEX, "w") as f:
        json.dump(index, f, indent=2)

def get_window_label(mode):
    mode_lower = mode.lower()
    if "open" in mode_lower:
        return "opening"
    elif "midday" in mode_lower or "mid" in mode_lower:
        return "midday"
    elif "close" in mode_lower or "pre-close" in mode_lower:
        return "closing"
    else:
        return "manual"

def save_daily_log(analysis_text, mode="Manual", tickers=None):
    ensure_logs_dir()
    today = datetime.now().strftime("%Y-%m-%d")
    time_now = datetime.now().strftime("%H:%M")
    window_label = get_window_label(mode)
    filename = f"{LOGS_DIR}/{today}_{window_label}.txt"

    lines = extract_key_points(analysis_text)

    with open(filename, "w") as f:
        f.write(f"{'='*50}\n")
        f.write(f"{mode.upper()} — {today} {time_now} GMT\n")
        if tickers:
            f.write(f"Assets: {', '.join(tickers)}\n")
        f.write(f"{'='*50}\n\n")
        f.write(lines)
        f.write("\n")

    index = load_index()
    if today not in index:
        index[today] = {
            "opening": None,
            "midday": None,
            "closing": None,
            "manual": []
        }

    if window_label == "manual":
        index[today]["manual"].append(filename)
    else:
        index[today][window_label] = filename

    save_index(index)
    return filename

def extract_key_points(analysis_text):
    lines = analysis_text.split("\n")
    output = []

    capture_sections = [
        "buy", "avoid", "watch",
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

def get_all_dates():
    index = load_index()
    return sorted(index.keys(), reverse=True)

def get_log_for_date_window(date, window):
    index = load_index()
    if date not in index:
        return None
    return index[date].get(window)

def read_log_file(filepath):
    if not filepath or not os.path.exists(filepath):
        return None
    with open(filepath, "r") as f:
        return f.read()

def delete_date_logs(date):
    index = load_index()
    if date not in index:
        return

    date_entry = index[date]
    for window in ["opening", "midday", "closing"]:
        filepath = date_entry.get(window)
        if filepath and os.path.exists(filepath):
            os.remove(filepath)

    for filepath in date_entry.get("manual", []):
        if filepath and os.path.exists(filepath):
            os.remove(filepath)

    del index[date]
    save_index(index)