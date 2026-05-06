#!/usr/bin/env python3
"""
Stock Price Agent v5
────────────────────
Real-time stock tracker with RELIABLE extended-hours support.
Parses actual trade candles (not meta summary fields) so
after-hours and pre-market moves always show up.

Sessions:
  🌅  Pre-Market    4:00 AM – 9:29 AM ET
  🔔  Regular       9:30 AM – 3:59 PM ET
  🌙  After Hours   4:00 PM – 7:59 PM ET
  💤  Overnight     8:00 PM – 3:59 AM ET

Usage:
    python stock_agent.py                     # default watchlist
    python stock_agent.py AAPL TSLA GOOG      # custom tickers

Requirements:
    pip install requests beautifulsoup4
"""

import sys
import re
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from html import unescape

DEFAULT_WATCHLIST = ["NBIS", "NVDA", "AMD", "META", "VXUS", "VOO", "SOXX"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

EXCHANGE_MAP = {
    "NBIS": "NASDAQ", "AMD": "NASDAQ", "META": "NASDAQ",
    "AAPL": "NASDAQ", "GOOG": "NASDAQ", "GOOGL": "NASDAQ",
    "MSFT": "NASDAQ", "AMZN": "NASDAQ", "TSLA": "NASDAQ",
    "NVDA": "NASDAQ", "NFLX": "NASDAQ", "IREN": "NASDAQ",
    "VOO": "NYSEARCA", "VXUS": "NASDAQ", "SPY": "NYSEARCA",
    "QQQ": "NASDAQ", "VTI": "NYSEARCA", "IWM": "NYSEARCA",
}

BULL_WORDS = [
    "surge", "soar", "jump", "rally", "gain", "rise", "bull",
    "upgrade", "beat", "record", "high", "boost", "buy",
    "outperform", "breakout", "growth", "strong", "positive",
    "optimis", "up ", "higher", "profit",
]
BEAR_WORDS = [
    "drop", "fall", "crash", "plunge", "sink", "bear", "sell",
    "downgrade", "miss", "low", "cut", "warn", "risk",
    "underperform", "loss", "weak", "negative", "pessimis",
    "down ", "lower", "decline", "fear", "slump", "tumble",
]


def arrow(c):  return "▲" if c > 0 else ("▼" if c < 0 else "─")
def sign(c):   return "+" if c >= 0 else ""

def clr(c, text):
    if c > 0: return f"\033[92m{text}\033[0m"
    if c < 0: return f"\033[91m{text}\033[0m"
    return text

def clr_bold(c, text):
    if c > 0: return f"\033[1;92m{text}\033[0m"
    if c < 0: return f"\033[1;91m{text}\033[0m"
    return f"\033[1m{text}\033[0m"

def fmt_vol(n):
    if n is None: return "N/A"
    if n >= 1e9:  return f"{n/1e9:,.2f}B"
    if n >= 1e6:  return f"{n/1e6:,.2f}M"
    if n >= 1e3:  return f"{n/1e3:,.1f}K"
    return f"{n:,.0f}"

def fmt_ts(epoch):
    if not epoch: return ""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%I:%M %p UTC")

def get_current_session():
    now = datetime.now()
    t = now.hour * 60 + now.minute
    if   240 <= t < 570:   return "pre_market",   "🌅  PRE-MARKET"
    elif 570 <= t < 960:   return "regular",      "🔔  MARKET OPEN"
    elif 960 <= t < 1200:  return "after_hours",  "🌙  AFTER HOURS"
    else:                  return "overnight",    "💤  OVERNIGHT"


# ── News ─────────────────────────────────────────────────────────────────────

def fetch_news(symbol, max_headlines=2):
    try:
        url = f"https://news.google.com/rss/search?q={symbol}+stock&hl=en-US&gl=US&ceid=US:en"
        resp = requests.get(url, headers=HEADERS, timeout=8)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        headlines = []
        for item in root.findall(".//item"):
            title = unescape(item.findtext("title", "").strip())
            title = re.sub(r'\s*[-–—]\s*[A-Za-z\s\.]+$', '', title)
            if title and len(title) > 10:
                headlines.append(title[:120])
            if len(headlines) >= max_headlines:
                break
        return headlines
    except Exception:
        return []

def sentiment_tag(headlines):
    text = " ".join(headlines).lower()
    bull = sum(1 for w in BULL_WORDS if w in text)
    bear = sum(1 for w in BEAR_WORDS if w in text)
    if bull > bear: return "\033[92m● Bullish\033[0m"
    if bear > bull: return "\033[91m● Bearish\033[0m"
    return "\033[93m● Neutral\033[0m"


# ── Yahoo Finance API — CANDLE-BASED PARSING ─────────────────────────────────

def _yahoo_get_crumb(session):
    session.get("https://fc.yahoo.com", headers=HEADERS, timeout=10, allow_redirects=True)
    r = session.get(
        "https://query2.finance.yahoo.com/v1/test/getcrumb",
        headers=HEADERS, timeout=10,
    )
    r.raise_for_status()
    return r.text.strip()


def _last_valid_close(closes, timestamps, start_ts, end_ts):
    """
    Walk backward through candles within [start_ts, end_ts) and return
    the last non-None close price and its timestamp.
    """
    for i in range(len(timestamps) - 1, -1, -1):
        ts = timestamps[i]
        if ts < start_ts or ts >= end_ts:
            continue
        c = closes[i]
        if c is not None:
            return c, ts
    return None, None


def _session_high_low_vol(highs, lows, volumes, timestamps, start_ts, end_ts):
    """Get high, low, total volume for candles in [start_ts, end_ts)."""
    h_list, l_list, v_total = [], [], 0
    for i, ts in enumerate(timestamps):
        if ts < start_ts or ts >= end_ts:
            continue
        if i < len(highs) and highs[i] is not None:
            h_list.append(highs[i])
        if i < len(lows) and lows[i] is not None:
            l_list.append(lows[i])
        if i < len(volumes) and volumes[i] is not None:
            v_total += volumes[i]
    return (max(h_list) if h_list else None,
            min(l_list) if l_list else None,
            v_total or None)


def fetch_yahoo(symbol, session=None, crumb=None):
    """
    Fetches quote by parsing ACTUAL TRADE CANDLES, not meta summaries.
    Uses currentTradingPeriod to classify each candle into its session.
    This catches after-hours moves even when meta.postMarketPrice is empty.
    """
    if session is None: session = requests.Session()
    if crumb is None:   crumb = _yahoo_get_crumb(session)

    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "range": "1d", "interval": "2m",
        "includePrePost": "true", "crumb": crumb,
    }
    resp = session.get(url, headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    result     = data["chart"]["result"][0]
    meta       = result["meta"]
    quotes     = result["indicators"]["quote"][0]
    timestamps = result.get("timestamp", [])
    closes     = quotes.get("close", [])
    highs_raw  = quotes.get("high", [])
    lows_raw   = quotes.get("low", [])
    vols_raw   = quotes.get("volume", [])

    prev_close = meta.get("chartPreviousClose") or meta.get("previousClose", 0)

    # Session boundaries from Yahoo's own trading period data
    ctp = meta.get("currentTradingPeriod", {})
    pre_start  = ctp.get("pre", {}).get("start", 0)
    pre_end    = ctp.get("pre", {}).get("end", 0)
    reg_start  = ctp.get("regular", {}).get("start", 0)
    reg_end    = ctp.get("regular", {}).get("end", 0)
    post_start = ctp.get("post", {}).get("start", 0)
    post_end   = ctp.get("post", {}).get("end", 0)

    # ── Parse candles for each session ───────────────────────────────
    reg_price, reg_time = _last_valid_close(closes, timestamps, reg_start, reg_end)
    if reg_price is None:
        reg_price = meta.get("regularMarketPrice", 0)
        reg_time  = meta.get("regularMarketTime", 0)

    ah_price, ah_time = _last_valid_close(closes, timestamps, post_start, post_end)
    if ah_price is None:
        mp = meta.get("postMarketPrice")
        if mp:
            ah_price, ah_time = mp, meta.get("postMarketTime", 0)

    pm_price, pm_time = _last_valid_close(closes, timestamps, pre_start, pre_end)
    if pm_price is None:
        mp = meta.get("preMarketPrice")
        if mp:
            pm_price, pm_time = mp, meta.get("preMarketTime", 0)

    # Absolute latest candle
    latest_price, latest_time = None, None
    for i in range(len(timestamps) - 1, -1, -1):
        if closes[i] is not None:
            latest_price, latest_time = closes[i], timestamps[i]
            break

    # Stats
    all_h = [h for h in highs_raw if h is not None]
    all_l = [l for l in lows_raw  if l is not None]
    all_v = [v for v in vols_raw  if v is not None]
    reg_high, reg_low, reg_vol = _session_high_low_vol(
        highs_raw, lows_raw, vols_raw, timestamps, reg_start, reg_end
    )

    return {
        "symbol": meta.get("symbol", symbol), "source": "Yahoo Finance",
        "prev_close": prev_close,
        "reg_price": reg_price or 0, "reg_time": reg_time or 0,
        "ah_price": ah_price, "ah_time": ah_time or 0,
        "pm_price": pm_price, "pm_time": pm_time or 0,
        "latest_price": latest_price, "latest_time": latest_time or 0,
        "1d_high": max(all_h) if all_h else None,
        "1d_low":  min(all_l) if all_l else None,
        "volume":  sum(all_v) if all_v else None,
        "reg_high": reg_high, "reg_low": reg_low, "reg_vol": reg_vol,
    }


# ── Fallbacks ────────────────────────────────────────────────────────────────

def fetch_google(symbol):
    exchange = EXCHANGE_MAP.get(symbol.upper(), "NASDAQ")
    url = f"https://www.google.com/finance/quote/{symbol}:{exchange}"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    price_el = soup.find("div", class_=lambda c: c and "YMlKec" in c and "fxKbKc" in c)
    if not price_el: raise ValueError("Could not parse price")
    price = float(price_el.text.strip().replace("$", "").replace(",", ""))
    chg = 0.0
    change_el = soup.find("div", class_=lambda c: c and "JwB6zf" in c)
    if change_el:
        for span in change_el.find_all("span"):
            txt = span.text.strip().replace("$", "").replace(",", "").replace("+", "")
            if "%" not in txt and txt and txt.replace("-", "").replace(".", "").isdigit():
                chg = float(txt); break
    return {
        "symbol": symbol.upper(), "source": "Google Finance",
        "prev_close": price - chg if chg else None,
        "reg_price": price, "reg_time": 0,
        "ah_price": None, "ah_time": 0, "pm_price": None, "pm_time": 0,
        "latest_price": price, "latest_time": 0,
        "1d_high": None, "1d_low": None, "volume": None,
        "reg_high": None, "reg_low": None, "reg_vol": None,
    }

def fetch_yahoo_scrape(symbol):
    url = f"https://finance.yahoo.com/quote/{symbol}/"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    def sv(field):
        el = soup.find("fin-streamer", {"data-field": field})
        if el and el.get("data-value"):
            try: return float(el["data-value"])
            except: pass
        return None
    reg = sv("regularMarketPrice")
    if reg is None: raise ValueError("Could not parse price")
    ah, pm = sv("postMarketPrice"), sv("preMarketPrice")
    return {
        "symbol": symbol.upper(), "source": "Yahoo (web)",
        "prev_close": None,
        "reg_price": reg, "reg_time": 0,
        "ah_price": ah, "ah_time": 0, "pm_price": pm, "pm_time": 0,
        "latest_price": ah or pm or reg, "latest_time": 0,
        "1d_high": None, "1d_low": None, "volume": None,
        "reg_high": None, "reg_low": None, "reg_vol": None,
    }

def fetch_quote(symbol, session=None, crumb=None):
    errors = []
    for name, fn in [
        ("Yahoo API",      lambda: fetch_yahoo(symbol, session, crumb)),
        ("Google Finance",  lambda: fetch_google(symbol)),
        ("Yahoo scrape",    lambda: fetch_yahoo_scrape(symbol)),
    ]:
        try: return fn()
        except Exception as e: errors.append(f"{name}: {e}")
    return {"symbol": symbol.upper(), "error": " | ".join(errors)}


# ── Current session logic ────────────────────────────────────────────────────

def compute_current(q, current_session):
    prev = q.get("prev_close") or 0
    reg  = q.get("reg_price") or 0
    ah   = q.get("ah_price")
    pm   = q.get("pm_price")
    latest = q.get("latest_price")

    if current_session == "pre_market":
        if pm:
            c = pm - prev if prev else 0
            p = (c / prev * 100) if prev else 0
            return pm, c, p, "🌅 Pre-Market"
        if ah:
            c = ah - reg if reg else 0
            p = (c / reg * 100) if reg else 0
            return ah, c, p, "🌅 Pre-Mkt (last AH)"
        c = reg - prev if prev else 0
        p = (c / prev * 100) if prev else 0
        return reg, c, p, "🌅 Pre-Mkt (prev close)"

    elif current_session == "regular":
        c = reg - prev if prev else 0
        p = (c / prev * 100) if prev else 0
        return reg, c, p, "🔔 Regular"

    elif current_session == "after_hours":
        if ah:
            c = ah - reg if reg else 0
            p = (c / reg * 100) if reg else 0
            return ah, c, p, "🌙 After Hours"
        c = reg - prev if prev else 0
        p = (c / prev * 100) if prev else 0
        return reg, c, p, "🌙 AH (at close)"

    elif current_session == "overnight":
        if ah:
            c = ah - reg if reg else 0
            p = (c / reg * 100) if reg else 0
            return ah, c, p, "💤 Overnight (AH close)"
        elif latest and latest != reg:
            c = latest - reg if reg else 0
            p = (c / reg * 100) if reg else 0
            return latest, c, p, "💤 Overnight"
        c = reg - prev if prev else 0
        p = (c / prev * 100) if prev else 0
        return reg, c, p, "💤 Overnight (at close)"

    c = reg - prev if prev else 0
    p = (c / prev * 100) if prev else 0
    return reg, c, p, "🔔 Regular"


# ── Display ──────────────────────────────────────────────────────────────────

def run(tickers):
    w = 72
    now = datetime.now()
    current_session, session_banner = get_current_session()

    print(f"\n{'='*w}")
    print("  📈  STOCK PRICE AGENT  v5")
    print(f"  {now.strftime('%A, %B %d %Y  %I:%M %p')}")
    print(f"  {session_banner}")
    print(f"{'='*w}")

    http_session = requests.Session()
    crumb = None
    try: crumb = _yahoo_get_crumb(http_session)
    except: pass

    results = [fetch_quote(tk, http_session, crumb) for tk in tickers]
    all_news = {tk: fetch_news(tk) for tk in tickers}

    for q in results:
        print()
        sym = q["symbol"]
        if "error" in q:
            print(f"  ❌  {sym}  —  Could not fetch data")
            print("  " + "─" * (w - 4))
            continue

        price, chg, pct, sess_label = compute_current(q, current_session)
        prev = q.get("prev_close") or 0
        reg  = q.get("reg_price") or 0

        chg_line = f"{arrow(chg)} {sign(chg)}{chg:,.2f} ({sign(pct)}{pct:.2f}%)"
        print(f"  {clr_bold(chg, sym):28s}  ${price:>10,.2f}   {sess_label}")
        print(f"  {'':>16}{clr_bold(chg, chg_line)}")
        print()

        if prev:
            print(f"      Prev Close    ${prev:>10,.2f}")

        pm = q.get("pm_price")
        if pm and prev:
            pc = pm - prev; pp = (pc / prev * 100) if prev else 0
            pm_str = f"${pm:>10,.2f}  {clr(pc, f'{sign(pc)}{pc:,.2f}  {sign(pp)}{pp:.2f}%')}  vs prev close"
            m = "  ◀ NOW" if current_session == "pre_market" else ""
            print(f"      🌅 Pre-Mkt    {pm_str}{m}")
        else:
            print(f"      🌅 Pre-Mkt     — no trades")

        if reg and prev:
            rc = reg - prev; rp = (rc / prev * 100) if prev else 0
            reg_str = f"${reg:>10,.2f}  {clr(rc, f'{sign(rc)}{rc:,.2f}  {sign(rp)}{rp:.2f}%')}  vs prev close"
            m = "  ◀ NOW" if current_session == "regular" else ""
            print(f"      🔔 Close      {reg_str}{m}")
        elif reg:
            print(f"      🔔 Close      ${reg:>10,.2f}")

        ah = q.get("ah_price")
        if ah and reg:
            ac = ah - reg; ap = (ac / reg * 100) if reg else 0
            ah_str = f"${ah:>10,.2f}  {clr(ac, f'{sign(ac)}{ac:,.2f}  {sign(ap)}{ap:.2f}%')}  vs close"
            m = "  ◀ NOW" if current_session in ("after_hours", "overnight") else ""
            print(f"      🌙 After Hrs  {ah_str}{m}")
            if prev:
                total_chg = ah - prev
                total_pct = (total_chg / prev * 100) if prev else 0
                print(f"      {'':>14}{clr(total_chg, f'Total day: {sign(total_chg)}{total_chg:,.2f}  {sign(total_pct)}{total_pct:.2f}% vs prev close')}")
        else:
            print(f"      🌙 After Hrs   — no trades")

        if current_session == "overnight":
            latest = q.get("latest_price")
            if latest and latest != reg and latest != ah:
                lc = latest - reg if reg else 0
                lp = (lc / reg * 100) if reg else 0
                print(f"      💤 Overnight  ${latest:>10,.2f}  {clr(lc, f'{sign(lc)}{lc:,.2f}  {sign(lp)}{lp:.2f}%')}  vs close  ◀ NOW")

        stats = []
        if q.get("reg_high") and q.get("reg_low"):
            stats.append(f"Reg: ${q['reg_low']:,.2f}–${q['reg_high']:,.2f}")
        if q.get("1d_high") and q.get("1d_low"):
            stats.append(f"Full: ${q['1d_low']:,.2f}–${q['1d_high']:,.2f}")
        if q.get("volume"):
            stats.append(f"Vol: {fmt_vol(q['volume'])}")
        if stats:
            print(f"      {'  │  '.join(stats)}")

        headlines = all_news.get(sym, [])
        if headlines:
            tag = sentiment_tag(headlines)
            print(f"\n      {tag}  Latest news:")
            for h in headlines[:2]:
                d = h if len(h) <= 72 else h[:69] + "..."
                print(f"        → {d}")
        else:
            print(f"\n      \033[93m● No recent news\033[0m")

        print("\n  " + "─" * (w - 4))

    valid = [q for q in results if "error" not in q]
    def cur_chg(q): _, c, _, _ = compute_current(q, current_session); return c
    def cur_pct(q): _, _, p, _ = compute_current(q, current_session); return p

    up = [q for q in valid if cur_chg(q) > 0]
    dn = [q for q in valid if cur_chg(q) < 0]
    fl = [q for q in valid if cur_chg(q) == 0]
    p = []
    if up: p.append(clr(1,  f"{len(up)} up"))
    if dn: p.append(clr(-1, f"{len(dn)} down"))
    if fl: p.append(f"{len(fl)} flat")
    if p:  print(f"\n  Summary:  {' · '.join(p)}")
    if up:
        b = max(up, key=cur_pct)
        print(f"  🏆 Best:   {b['symbol']} ({sign(cur_pct(b))}{cur_pct(b):.2f}%)")
    if dn:
        w2 = min(dn, key=cur_pct)
        print(f"  💔 Worst:  {w2['symbol']} ({cur_pct(w2):.2f}%)")
    print(f"\n{'='*w}\n")


if __name__ == "__main__":
    tickers = [t.upper() for t in (sys.argv[1:] or DEFAULT_WATCHLIST)]
    run(tickers)