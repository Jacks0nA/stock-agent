import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def get_options_flow(ticker):
    try:
        stock = yf.Ticker(ticker)
        
        expirations = stock.options
        if not expirations:
            return None
        
        near_expiry = expirations[:3]
        
        unusual_activity = []
        
        for expiry in near_expiry:
            try:
                chain = stock.option_chain(expiry)
                calls = chain.calls
                puts = chain.puts
                
                current_price = stock.fast_info.last_price
                
                calls = calls[
                    (calls["volume"] > 100) &
                    (calls["volume"] > calls["openInterest"] * 0.5)
                ].copy()
                
                puts = puts[
                    (puts["volume"] > 100) &
                    (puts["volume"] > puts["openInterest"] * 0.5)
                ].copy()
                
                for _, row in calls.iterrows():
                    try:
                        strike = row["strike"]
                        volume = row["volume"]
                        open_interest = row["openInterest"]
                        iv = row["impliedVolatility"]
                        premium = row["lastPrice"]
                        total_value = volume * premium * 100
                        
                        pct_otm = ((strike - current_price) / current_price) * 100
                        
                        if volume > 500 or total_value > 100000:
                            signal = "🟢 BULLISH"
                        else:
                            signal = "⚪ MODERATE BULLISH"
                        
                        unusual_activity.append({
                            "type": "CALL",
                            "signal": signal,
                            "expiry": expiry,
                            "strike": strike,
                            "volume": int(volume),
                            "open_interest": int(open_interest),
                            "iv": round(iv * 100, 1),
                            "premium": premium,
                            "total_value": round(total_value, 0),
                            "pct_otm": round(pct_otm, 1)
                        })
                    except Exception:
                        continue
                
                for _, row in puts.iterrows():
                    try:
                        strike = row["strike"]
                        volume = row["volume"]
                        open_interest = row["openInterest"]
                        iv = row["impliedVolatility"]
                        premium = row["lastPrice"]
                        total_value = volume * premium * 100
                        
                        pct_otm = ((current_price - strike) / current_price) * 100
                        
                        if volume > 500 or total_value > 100000:
                            signal = "🔴 BEARISH"
                        else:
                            signal = "⚪ MODERATE BEARISH"
                        
                        unusual_activity.append({
                            "type": "PUT",
                            "signal": signal,
                            "expiry": expiry,
                            "strike": strike,
                            "volume": int(volume),
                            "open_interest": int(open_interest),
                            "iv": round(iv * 100, 1),
                            "premium": premium,
                            "total_value": round(total_value, 0),
                            "pct_otm": round(pct_otm, 1)
                        })
                    except Exception:
                        continue
            
            except Exception:
                continue
        
        if not unusual_activity:
            return None
        
        unusual_activity.sort(key=lambda x: x["total_value"], reverse=True)
        return unusual_activity[:5]
    
    except Exception:
        return None

def get_options_summary(tickers):
    summary = {}
    
    for ticker in tickers:
        flow = get_options_flow(ticker)
        if flow:
            calls = [f for f in flow if f["type"] == "CALL"]
            puts = [f for f in flow if f["type"] == "PUT"]
            
            call_value = sum(f["total_value"] for f in calls)
            put_value = sum(f["total_value"] for f in puts)
            
            if call_value > put_value * 2:
                overall = "🟢 BULLISH OPTIONS FLOW"
            elif put_value > call_value * 2:
                overall = "🔴 BEARISH OPTIONS FLOW"
            else:
                overall = "⚪ MIXED OPTIONS FLOW"
            
            summary[ticker] = {
                "flow": flow,
                "call_value": call_value,
                "put_value": put_value,
                "overall": overall
            }
    
    return summary

def format_options_string(options_summary):
    if not options_summary:
        return "No unusual options activity detected."
    
    result = "UNUSUAL OPTIONS ACTIVITY:\n"
    
    for ticker, data in options_summary.items():
        result += f"\n{ticker} — {data['overall']}\n"
        result += f"  Total call value: ${data['call_value']:,.0f}\n"
        result += f"  Total put value: ${data['put_value']:,.0f}\n"
        for flow in data["flow"][:3]:
            result += f"  {flow['signal']} {flow['type']} — Strike ${flow['strike']} exp {flow['expiry']} — Vol {flow['volume']:,} — ${flow['total_value']:,.0f} — IV {flow['iv']}%\n"
    
    return result

if __name__ == "__main__":
    test_tickers = ["AAPL", "NVDA", "TSLA", "SPY", "GE", "PLTR"]
    print(f"Fetching options flow for {len(test_tickers)} stocks...")
    summary = get_options_summary(test_tickers)
    print(format_options_string(summary))
    if summary:
        print(f"\nFound unusual activity in {len(summary)} stocks")
    else:
        print("\nNo unusual options activity found")