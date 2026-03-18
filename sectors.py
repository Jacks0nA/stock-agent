import yfinance as yf
import pandas as pd
from datetime import datetime

BENCHMARKS = {
    "SPY": "S&P 500 — broad market",
    "QQQ": "NASDAQ 100 — tech heavy",
    "DIA": "Dow Jones — blue chip",
    "IWM": "Russell 2000 — small cap",
    "XLK": "Tech sector ETF",
    "XLF": "Finance sector ETF",
    "XLE": "Energy sector ETF",
    "XLV": "Healthcare sector ETF",
    "XLY": "Consumer discretionary ETF"
}

def get_market_context():
    context = {}
    
    for ticker, description in BENCHMARKS.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            hist.index = hist.index.tz_localize(None)
            
            if len(hist) >= 2:
                prev_close = hist["Close"].iloc[-2]
                current = hist["Close"].iloc[-1]
                change_percent = round(((current - prev_close) / prev_close) * 100, 2)
                direction = "▲" if change_percent > 0 else "▼"
                
                context[ticker] = {
                    "description": description,
                    "price": round(current, 2),
                    "change_percent": change_percent,
                    "direction": direction
                }
        
        except Exception as e:
            context[ticker] = None
    
    return context

def get_market_summary(context):
    summary = "Current market context:\n"
    
    spy = context.get("SPY")
    qqq = context.get("QQQ")
    
    if spy:
        summary += f"S&P 500 (SPY): {spy['direction']} {spy['change_percent']}%\n"
    if qqq:
        summary += f"NASDAQ (QQQ): {qqq['direction']} {qqq['change_percent']}%\n"
    
    if spy and qqq:
        if spy['change_percent'] > 0.5 and qqq['change_percent'] > 0.5:
            summary += "Overall market: Strong broad rally — rising tide lifting all boats\n"
        elif spy['change_percent'] < -0.5 and qqq['change_percent'] < -0.5:
            summary += "Overall market: Broad selloff — macro headwinds affecting all sectors\n"
        elif abs(spy['change_percent']) < 0.2:
            summary += "Overall market: Flat/directionless — stock picking environment\n"
        else:
            summary += "Overall market: Mixed signals — sector rotation likely\n"
    
    summary += "\nSector ETF performance:\n"
    for ticker, data in context.items():
        if ticker not in ["SPY", "QQQ", "DIA", "IWM"] and data:
            summary += f"  {ticker} ({data['description']}): {data['direction']} {data['change_percent']}%\n"
    
    return summary

if __name__ == "__main__":
    context = get_market_context()
    print(get_market_summary(context))