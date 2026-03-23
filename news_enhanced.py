import os
import re
import feedparser
import httpx
import yfinance as yf
from datetime import datetime, timezone, timedelta
from textblob import TextBlob
from dotenv import load_dotenv

load_dotenv()

# Reuters RSS feeds by category
REUTERS_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/technologyNews",
    "https://feeds.reuters.com/reuters/health",
    "https://feeds.reuters.com/reuters/energyNews",
]

# Motley Fool earnings summary base URL
MOTLEY_FOOL_BASE = "https://www.fool.com/earnings/"

def get_sentiment(text):
    analysis = TextBlob(text)
    score = analysis.sentiment.polarity
    if score > 0.1:
        return "Positive", round(score, 2)
    elif score < -0.1:
        return "Negative", round(score, 2)
    else:
        return "Neutral", round(score, 2)

def get_article_age_hours(published_str):
    """
    Returns how many hours ago an article was published.
    Returns 999 if unparseable.
    """
    try:
        import email.utils
        dt = email.utils.parsedate_to_datetime(published_str)
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        age = datetime.utcnow() - dt
        return age.total_seconds() / 3600
    except Exception:
        return 999

def get_recency_weight(hours_old):
    """
    Returns a weight multiplier based on article age.
    Recent articles weighted higher.
    """
    if hours_old < 2:
        return 2.0
    elif hours_old < 6:
        return 1.5
    elif hours_old < 24:
        return 1.0
    elif hours_old < 48:
        return 0.75
    else:
        return 0.5

def fetch_reuters_headlines(ticker, company_name=None):
    """
    Fetches Reuters RSS headlines relevant to ticker or company name.
    Returns list of dicts with title, summary, published, age_hours.
    """
    results = []
    search_terms = [ticker.replace("-USD", "").replace("=F", "")]
    if company_name:
        search_terms.append(company_name.lower())

    for feed_url in REUTERS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                published = entry.get("published", "")

                combined = (title + " " + summary).lower()
                if any(term.lower() in combined for term in search_terms):
                    age_hours = get_article_age_hours(published)
                    results.append({
                        "title": title,
                        "summary": summary[:300] if summary else "",
                        "source": "Reuters",
                        "published": published,
                        "age_hours": age_hours
                    })
        except Exception:
            continue

    return results

def fetch_yahoo_headlines_enhanced(ticker):
    """
    Fetches Yahoo Finance headlines with first paragraph where available.
    """
    results = []
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        for article in news[:5]:
            title = ""
            summary = ""
            published = ""

            if "title" in article:
                title = article["title"]
            elif "content" in article and "title" in article.get("content", {}):
                title = article["content"]["title"]

            if "summary" in article:
                summary = article["summary"][:300]
            elif "content" in article and "summary" in article.get("content", {}):
                summary = article["content"]["summary"][:300]

            published_ts = article.get("providerPublishTime", 0)
            if published_ts:
                age_hours = (datetime.utcnow() - datetime.utcfromtimestamp(published_ts)).total_seconds() / 3600
            else:
                age_hours = 999

            if title:
                results.append({
                    "title": title,
                    "summary": summary,
                    "source": "Yahoo Finance",
                    "published": published,
                    "age_hours": age_hours
                })
    except Exception:
        pass
    return results

def fetch_newsapi_headlines_enhanced(ticker, client):
    """
    Fetches NewsAPI headlines with recency weighting.
    """
    results = []
    try:
        articles = client.get_everything(
            q=ticker,
            language="en",
            sort_by="publishedAt",
            page_size=5
        )
        for a in articles["articles"]:
            title = a.get("title", "")
            description = a.get("description", "")[:300] if a.get("description") else ""
            published = a.get("publishedAt", "")

            try:
                dt = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
                age_hours = (datetime.utcnow() - dt).total_seconds() / 3600
            except Exception:
                age_hours = 999

            if title:
                results.append({
                    "title": title,
                    "summary": description,
                    "source": "NewsAPI",
                    "published": published,
                    "age_hours": age_hours
                })
    except Exception:
        pass
    return results

def fetch_earnings_summary(ticker):
    """
    Fetches recent earnings summary from Motley Fool.
    Returns a brief summary string or None.
    """
    try:
        url = f"https://www.fool.com/quote/{ticker.lower()}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; stock-agent/1.0)"
        }
        response = httpx.get(url, headers=headers, timeout=8, follow_redirects=True)
        if response.status_code != 200:
            return None

        text = response.text
        # Extract earnings related sentences
        earnings_keywords = ["earnings", "revenue", "beat", "miss", "guidance", "EPS", "quarterly"]
        sentences = re.split(r'(?<=[.!?])\s+', text)
        relevant = []
        for sentence in sentences:
            clean = re.sub(r'<[^>]+>', '', sentence).strip()
            if any(kw.lower() in clean.lower() for kw in earnings_keywords):
                if 20 < len(clean) < 300:
                    relevant.append(clean)
            if len(relevant) >= 3:
                break

        if relevant:
            return " ".join(relevant)
        return None
    except Exception:
        return None

def fetch_stock_news_enhanced(tickers):
    """
    Enhanced news fetching with Reuters, publication time weighting,
    first paragraphs, and earnings summaries.
    """
    try:
        from newsapi import NewsApiClient
        news_client = NewsApiClient(api_key=os.getenv("NEWS_API_KEY"))
        newsapi_available = True
    except Exception:
        newsapi_available = False
        news_client = None

    all_news = {}

    for ticker in tickers:
        try:
            all_articles = []

            # Yahoo Finance
            yahoo = fetch_yahoo_headlines_enhanced(ticker)
            all_articles.extend(yahoo)

            # Reuters
            reuters = fetch_reuters_headlines(ticker)
            all_articles.extend(reuters)

            # NewsAPI
            if newsapi_available and news_client:
                newsapi = fetch_newsapi_headlines_enhanced(ticker, news_client)
                all_articles.extend(newsapi)

            if not all_articles:
                all_news[ticker] = {
                    "headlines": [{"title": "No news found", "sentiment": "Neutral", "score": 0, "age_hours": 999, "summary": ""}],
                    "overall_sentiment": "Neutral",
                    "avg_score": 0,
                    "has_signal": False,
                    "earnings_summary": None
                }
                continue

            # Sort by recency
            all_articles.sort(key=lambda x: x.get("age_hours", 999))

            # Score with recency weighting
            scored_headlines = []
            weighted_scores = []

            for article in all_articles[:8]:
                title = article["title"]
                summary = article.get("summary", "")
                age_hours = article.get("age_hours", 999)
                recency_weight = get_recency_weight(age_hours)

                # Score on title + summary combined
                combined_text = title + " " + summary
                sentiment_label, raw_score = get_sentiment(combined_text)
                weighted_score = raw_score * recency_weight

                # Format age display
                if age_hours < 1:
                    age_str = f"{int(age_hours * 60)}m ago"
                elif age_hours < 24:
                    age_str = f"{int(age_hours)}h ago"
                else:
                    age_str = f"{int(age_hours / 24)}d ago"

                scored_headlines.append({
                    "title": title,
                    "summary": summary,
                    "sentiment": sentiment_label,
                    "score": round(raw_score, 2),
                    "weighted_score": round(weighted_score, 2),
                    "age_hours": age_hours,
                    "age_str": age_str,
                    "source": article.get("source", "Unknown")
                })
                weighted_scores.append(weighted_score)

            avg_score = round(sum(weighted_scores) / len(weighted_scores), 2) if weighted_scores else 0

            if avg_score > 0.1:
                overall_sentiment = "Positive"
            elif avg_score < -0.1:
                overall_sentiment = "Negative"
            else:
                overall_sentiment = "Neutral"

            # Fetch earnings summary
            earnings_summary = fetch_earnings_summary(ticker)

            all_news[ticker] = {
                "headlines": scored_headlines,
                "overall_sentiment": overall_sentiment,
                "avg_score": avg_score,
                "has_signal": abs(avg_score) > 0.1,
                "earnings_summary": earnings_summary
            }

        except Exception:
            all_news[ticker] = {
                "headlines": [{"title": "No news found", "sentiment": "Neutral", "score": 0, "age_hours": 999, "summary": ""}],
                "overall_sentiment": "Neutral",
                "avg_score": 0,
                "has_signal": False,
                "earnings_summary": None
            }

    return all_news