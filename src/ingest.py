"""Data ingestion: spot prices, option chains and earnings dates via yfinance.

Design note: every function degrades gracefully. Missing earnings dates,
empty chains or bad quotes are surfaced as explicit flags downstream
instead of being silently filled -- that honesty is the point of the
data-quality layer (see metrics.py).
"""
from __future__ import annotations

import datetime as dt

import yfinance as yf


def get_spot(ticker: str) -> float:
    t = yf.Ticker(ticker)
    try:
        px = (t.fast_info or {}).get("last_price")
        if px:
            return float(px)
    except Exception:
        pass
    hist = t.history(period="2d")
    return float(hist["Close"].iloc[-1])


def get_expirations(ticker: str) -> list[str]:
    return list(yf.Ticker(ticker).options or [])


def get_earnings_date(ticker: str) -> tuple[dt.date | None, bool]:
    """Return (earnings_date, is_estimated).

    yfinance earnings calendars are patchy: future dates are often absent
    and past dates get recycled as estimates. We never invent precision --
    when the source has nothing usable we return (None, True) and the
    caller falls back to a ~30-day baseline expiry.
    """
    if ticker == "SPY":  # index product: no earnings, use ~30d baseline
        return None, True
    t = yf.Ticker(ticker)
    try:
        df = t.get_earnings_dates(limit=8)
        if df is not None and not df.empty:
            idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
            today = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            future = df[idx >= today]
            if not future.empty:
                return future.index[0].date(), False
    except Exception:
        pass
    return None, True


def choose_expiry(ticker: str, earnings_date: dt.date | None) -> str:
    """Pick the cross-earnings expiry: nearest expiry on/after earnings.

    Falls back to the expiry nearest ~30 days out when no earnings date
    is known (SPY, missing calendar data).
    """
    exps = sorted(dt.date.fromisoformat(e) for e in get_expirations(ticker))
    today = dt.date.today()
    exps = [e for e in exps if e > today]
    if not exps:
        raise ValueError(f"{ticker}: no expirations available")
    if earnings_date:
        after = [e for e in exps if e >= earnings_date]
        if after:
            return after[0].isoformat()
    target = today + dt.timedelta(days=30)
    return min(exps, key=lambda e: abs((e - target).days)).isoformat()


def get_chain(ticker: str, expiry: str):
    """Return (calls, puts) DataFrames with bid/ask NaNs zeroed."""
    calls, puts = yf.Ticker(ticker).option_chain(expiry)
    for df in (calls, puts):
        for col in ("bid", "ask"):
            if col in df.columns:
                df[col] = df[col].fillna(0.0)
    return calls, puts


def get_closes(ticker: str, trading_days: int) -> list[float]:
    hist = yf.Ticker(ticker).history(period=f"{trading_days + 10}d")
    closes = hist["Close"].dropna().tolist()
    return [float(c) for c in closes[-(trading_days + 1):]]
