from newsapi import NewsApiClient
import yfinance as yf
import os
from dotenv import load_dotenv
from textblob import TextBlob

load_dotenv()

def get_sentiment(text):
    analysis = TextBlob(text)
    score = analysis.sentiment.polarity
    if score > 0.1:
        return "Positive", round(score, 2)
    elif score < -0.1:
        return "Negative", round(score, 2)
    else:
        return "Neutral", round(score, 2)

def fetch_newsapi_headlines(ticker, client):
    try:
        articles = client.get_everything(
            q=ticker,
            language="en",
            sort_by="publishedAt",
            page_size=3
        )
        return [a["title"] for a in articles["articles"]]
    except Exception:
        return []

def fetch_yahoo_headlines(ticker):
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        headlines = []
        for article in news[:3]:
            if "title" in article:
                headlines.append(article["title"])
            elif "content" in article and "title" in article.get("content", {}):
                headlines.append(article["content"]["title"])
        return headlines
    except Exception:
        return []

def fetch_stock_news(tickers):
    try:
        news_client = NewsApiClient(api_key=os.getenv("NEWS_API_KEY"))
        newsapi_available = True
    except Exception:
        newsapi_available = False
        news_client = None

    all_news = {}

    for ticker in tickers:
        try:
            headlines = []
            yahoo_headlines = fetch_yahoo_headlines(ticker)
            headlines.extend(yahoo_headlines)

            if newsapi_available and news_client:
                newsapi_headlines = fetch_newsapi_headlines(ticker, news_client)
                for h in newsapi_headlines:
                    if h not in headlines:
                        headlines.append(h)

            if not headlines:
                headlines = ["No news found"]

            scored_headlines = []
            scores = []

            for title in headlines:
                sentiment_label, sentiment_score = get_sentiment(title)
                scored_headlines.append({
                    "title": title,
                    "sentiment": sentiment_label,
                    "score": sentiment_score
                })
                scores.append(sentiment_score)

            avg_score = round(sum(scores) / len(scores), 2) if scores else 0

            if avg_score > 0.1:
                overall_sentiment = "Positive"
            elif avg_score < -0.1:
                overall_sentiment = "Negative"
            else:
                overall_sentiment = "Neutral"

            all_news[ticker] = {
                "headlines": scored_headlines,
                "overall_sentiment": overall_sentiment,
                "avg_score": avg_score,
                "has_signal": abs(avg_score) > 0.1
            }

        except Exception:
            all_news[ticker] = {
                "headlines": [{"title": "No news found", "sentiment": "Neutral", "score": 0}],
                "overall_sentiment": "Neutral",
                "avg_score": 0,
                "has_signal": False
            }

    return all_news