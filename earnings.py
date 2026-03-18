import yfinance as yf
from datetime import datetime, timedelta

def get_earnings_calendar(tickers):
    earnings = {}
    today = datetime.now()
    week_ahead = today + timedelta(days=7)
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            calendar = stock.calendar
            
            if calendar is not None and len(calendar) > 0:
                if 'Earnings Date' in calendar:
                    earnings_date = calendar['Earnings Date']
                    
                    if isinstance(earnings_date, list):
                        earnings_date = earnings_date[0]
                    
                    if hasattr(earnings_date, 'to_pydatetime'):
                        earnings_date = earnings_date.to_pydatetime()
                    
                    earnings_date = earnings_date.replace(tzinfo=None)
                    
                    days_until = (earnings_date - today).days
                    
                    if 0 <= days_until <= 7:
                        earnings[ticker] = {
                            "date": earnings_date.strftime("%Y-%m-%d"),
                            "days_until": days_until,
                            "warning": f"⚠️ Earnings in {days_until} days"
                        }
                    elif days_until > 7:
                        earnings[ticker] = {
                            "date": earnings_date.strftime("%Y-%m-%d"),
                            "days_until": days_until,
                            "warning": None
                        }
            else:
                earnings[ticker] = None
                
        except Exception as e:
            earnings[ticker] = None
    
    return earnings

def get_earnings_summary(earnings):
    upcoming = []
    for ticker, data in earnings.items():
        if data and data.get("days_until") is not None and data["days_until"] <= 7:
            upcoming.append(f"{ticker} reports in {data['days_until']} days ({data['date']})")
    
    if not upcoming:
        return "No earnings reports in the next 7 days for tracked stocks."
    
    return "Upcoming earnings:\n" + "\n".join(upcoming)

if __name__ == "__main__":
    tickers = ["AAPL", "GOOGL", "NVDA", "MSFT", "AMZN"]
    earnings = get_earnings_calendar(tickers)
    print(get_earnings_summary(earnings))
    print("\nFull calendar:")
    for ticker, data in earnings.items():
        if data:
            print(f"  {ticker}: {data['date']} ({data['days_until']} days away)")
