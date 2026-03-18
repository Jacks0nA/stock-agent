import yfinance as yf
import pandas as pd

def calculate_rsi(closes, period=14):
    delta = closes.diff()
    gains = delta.where(delta > 0, 0)
    losses = -delta.where(delta < 0, 0)
    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi.iloc[-1], 2)

def fetch_stock_data(tickers):
    data = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            hist.index = hist.index.tz_localize(None)
            
            if len(hist) >= 2:
                prev_close = hist["Close"].iloc[-2]
                current_price = hist["Close"].iloc[-1]
                change = current_price - prev_close
                change_percent = (change / prev_close) * 100
                direction = "▲" if change > 0 else "▼"
            else:
                current_price = hist["Close"].iloc[-1]
                change = 0
                change_percent = 0
                direction = "—"
            
            data.append({
                "ticker": ticker,
                "price": round(current_price, 2),
                "change": round(change, 2),
                "change_%": round(change_percent, 2),
                "direction": direction
            })
        
        except Exception as e:
            data.append({
                "ticker": ticker,
                "price": "N/A",
                "change": "N/A",
                "change_%": "N/A",
                "direction": "—"
            })
    
    return pd.DataFrame(data)

def fetch_historical_data(tickers):
    historical = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            hist.index = hist.index.tz_localize(None)
            
            closes = hist["Close"]
            ma20 = round(closes.rolling(window=20).mean().iloc[-1], 2)
            ma50 = round(closes.rolling(window=50).mean().iloc[-1], 2)
            current = round(closes.iloc[-1], 2)
            rsi = calculate_rsi(closes)
            avg_volume = round(hist["Volume"].rolling(window=20).mean().iloc[-1])
            today_volume = hist["Volume"].iloc[-1]
            volume_signal = "High volume" if today_volume > avg_volume * 1.5 else "Normal volume"

            if rsi > 70:
                rsi_signal = "Overbought"
            elif rsi < 30:
                rsi_signal = "Oversold"
            else:
                rsi_signal = "Neutral"

            import math
            if math.isnan(ma20) or math.isnan(ma50):
                ma_signal = "Insufficient data"
                ma20 = "N/A"
                ma50 = "N/A"
            else:
                ma_signal = "Above both MAs — bullish" if current > ma20 and current > ma50 else \
                            "Below both MAs — bearish" if current < ma20 and current < ma50 else \
                            "Mixed signals"

            historical[ticker] = {
                "high_30d": round(closes.tail(30).max(), 2),
                "low_30d": round(closes.tail(30).min(), 2),
                "avg_30d": round(closes.tail(30).mean(), 2),
                "trend": "▲ Uptrend" if closes.iloc[-1] > closes.iloc[0] else "▼ Downtrend",
                "ma20": ma20,
                "ma50": ma50,
                "rsi": rsi,
                "rsi_signal": rsi_signal,
                "ma_signal": ma_signal,
                "volume_signal": volume_signal
            }
        
        except Exception as e:
            historical[ticker] = {}
    
    return historical

if __name__ == "__main__":
    tickers = ["AAPL", "GOOGL", "NVDA"]
    df = fetch_stock_data(tickers)
    print(df)
    
    historical = fetch_historical_data(tickers)
    for ticker, data in historical.items():
        print(f"\n{ticker}:")
        print(f"  RSI: {data['rsi']} — {data['rsi_signal']}")
        print(f"  MA20: {data['ma20']}  MA50: {data['ma50']}")
        print(f"  Signal: {data['ma_signal']}")
        print(f"  Volume: {data['volume_signal']}")
