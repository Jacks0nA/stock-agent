import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from io import StringIO

HEADERS = {
    "User-Agent": "stock-agent research@example.com"
}

COMPANY_CIKS = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "NVDA": "0001045810",
    "GOOGL": "0001652044",
    "AMZN": "0001018724",
    "META": "0001326801",
    "TSLA": "0001318605",
    "JPM": "0000019617",
    "BAC": "0000070858",
    "GS": "0000886982",
    "V": "0001403161",
    "WMT": "0000104169",
    "PFE": "0000078003",
    "GE": "0000040533",
    "MCD": "0000063908",
    "SCHW": "0000316709",
    "VLO": "0001035002",
    "MDB": "0001441816",
    "HAL": "0000045012",
    "OVV": "0001792789",
    "SYK": "0000310764",
    "MMM": "0000066740",
    "AMD": "0000002488",
    "VRTX": "0000875320",
    "PSX": "0001534992",
    "NOC": "0001133421",
    "CAT": "0000018230",
    "DE": "0000315189",
    "HON": "0000773840",
    "FDX": "0001048911",
    "COP": "0001163165",
    "EOG": "0000821189",
    "MPC": "0000101778",
    "OXY": "0000797468",
    "NKE": "0000320187",
    "SBUX": "0000829224",
    "TJX": "0000109198",
    "YUM": "0001041514",
    "PYPL": "0001633917",
    "UBER": "0001543151",
    "PLTR": "0001321655",
    "NET": "0001477333",
    "ZM": "0001585583",
    "OKTA": "0001660134",
    "CRM": "0001108524",
    "NFLX": "0001065280",
    "INTC": "0000050863",
    "SNAP": "0001564408",
    "BMY": "0000014272",
    "GILD": "0000882184",
    "BIIB": "0000875045",
    "ABBV": "0001551152",
    "MRK": "0000310158",
    "ABT": "0000001800",
    "DHR": "0000313616",
    "AMGN": "0000318154",
    "MDT": "0001613103",
    "COF": "0000927628",
    "USB": "0000036104",
    "BK": "0000009626",
    "RF": "0001281761",
    "CFG": "0001378946",
    "SM": "0000893538",
    "APA": "0000006769",
    "BKR": "0001701605",
    "DVN": "0001090012",
    "ROK": "0001024478",
    "DOV": "0000029905",
    "XYL": "0001524472",
    "AME": "0001037868",
    "EMR": "0000032604",
    "PH": "0000076334",
    "GD": "0000040533",
    "ROST": "0000745732",
    "DG": "0000935703",
    "DLTR": "0000935703",
    "DPZ": "0001286681",
    "QSR": "0001618756",
    "SPOT": "0001639920",
    "SHOP": "0001594805",
    "RBLX": "0001315098",
    "DOCU": "0001261333",
    "TWLO": "0001621221",
    "SNOW": "0001640147",
}

GENUINE_BUY_CODES = ["P"]
IGNORE_CODES = ["M", "F", "A", "G", "J", "K", "L", "U", "X", "Z"]

def get_xml_from_filing(acc, cik):
    try:
        acc_clean = acc.replace("-", "")
        cik_int = int(cik)
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{acc}-index.htm"
        r = requests.get(index_url, headers=HEADERS, timeout=10)

        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        xml_url = None

        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.endswith(".xml") and "xsl" not in href.lower():
                xml_url = f"https://www.sec.gov{href}"
                break

        if not xml_url:
            return None

        xml_r = requests.get(xml_url, headers=HEADERS, timeout=10)
        if xml_r.status_code != 200:
            return None

        return xml_r.text

    except Exception:
        return None

def parse_form4(xml_text, filing_date):
    try:
        root = ET.fromstring(xml_text)

        insider_name = None
        title = None

        for elem in root.iter("rptOwnerName"):
            insider_name = elem.text
            break

        for elem in root.iter("officerTitle"):
            title = elem.text
            break

        if not title:
            for elem in root.iter("isDirector"):
                if elem.text == "1":
                    title = "Director"
                    break

        purchases = []

        for trans in root.iter("nonDerivativeTransaction"):
            code_elem = trans.find(".//transactionCode")
            if code_elem is None:
                continue

            code = code_elem.text.strip()
            if code not in GENUINE_BUY_CODES:
                continue

            shares_elem = trans.find(".//transactionShares/value")
            price_elem = trans.find(".//transactionPricePerShare/value")

            try:
                shares = float(shares_elem.text) if shares_elem is not None else None
                price = float(price_elem.text) if price_elem is not None else None
            except Exception:
                continue

            if shares and price and price > 0:
                purchases.append({
                    "date": filing_date,
                    "insider": insider_name or "Unknown",
                    "title": title or "Unknown",
                    "shares": shares,
                    "price": price,
                    "value": round(shares * price, 2)
                })

        return purchases

    except Exception:
        return []

def get_insider_trades(ticker, max_filings=8):
    try:
        cik = COMPANY_CIKS.get(ticker)
        if not cik:
            return None

        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        response = requests.get(url, headers={
            **HEADERS,
            "Host": "data.sec.gov"
        }, timeout=10)

        if response.status_code != 200:
            return None

        data = response.json()
        filings = data.get("filings", {}).get("recent", {})

        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        accessions = filings.get("accessionNumber", [])

        cutoff = datetime.now() - timedelta(days=90)
        all_purchases = []
        checked = 0

        for i, form in enumerate(forms):
            if form != "4":
                continue

            try:
                filing_date = datetime.strptime(dates[i], "%Y-%m-%d")
            except Exception:
                continue

            if filing_date < cutoff:
                break

            if checked >= max_filings:
                break

            checked += 1

            xml_text = get_xml_from_filing(accessions[i], cik)
            if not xml_text:
                continue

            purchases = parse_form4(xml_text, dates[i])
            all_purchases.extend(purchases)

        return all_purchases if all_purchases else None

    except Exception:
        return None

def get_insider_summary(tickers):
    summary = {}

    for ticker in tickers:
        trades = get_insider_trades(ticker)

        if trades:
            total_value = sum(t["value"] for t in trades)
            num_trades = len(trades)

            if total_value > 500000:
                signal = "🟢 STRONG — Major insider buying"
            elif total_value > 50000:
                signal = "🟡 MODERATE — Notable insider buying"
            else:
                signal = "⚪ MINOR — Small insider buying"

            summary[ticker] = {
                "trades": trades,
                "total_value": total_value,
                "num_trades": num_trades,
                "signal": signal
            }

    return summary

def format_insider_string(insider_summary):
    if not insider_summary:
        return "No genuine insider purchases detected in the last 90 days."

    result = "INSIDER BUYING (SEC Form 4 — cash purchases only, last 90 days):\n"

    for ticker, data in insider_summary.items():
        result += f"\n{ticker} — {data['signal']}\n"
        result += f"  Total: ${data['total_value']:,.0f} across {data['num_trades']} trades\n"
        for trade in data["trades"][:3]:
            result += f"  {trade['date']} — {trade['insider']} ({trade['title']}) bought {trade['shares']:,.0f} shares @ ${trade['price']:.2f}\n"

    return result

if __name__ == "__main__":
    test_tickers = ["GE", "SCHW", "VLO", "HAL", "OVV", "JPM", "BAC", "PSX", "MMM", "FDX"]
    print(f"Fetching genuine insider purchases for {len(test_tickers)} stocks...")
    print("This will take 1-2 minutes...\n")
    summary = get_insider_summary(test_tickers)
    print(format_insider_string(summary))
    if summary:
        print(f"\nFound genuine buying in {len(summary)} stocks")
    else:
        print("\nNo cash purchases found — executives receiving stock grants only")