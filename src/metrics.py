"""Core pricing metrics.

Pipeline per ticker:
    spot -> ATM strike -> straddle -> implied move
                                        \
                                         richness = implied / realized (same horizon)
                                        /
    recent closes -> realized daily vol, scaled to DTE

Verdicts:
    richness > 1.2  -> "rich"    (implied running hot vs recent realized)
    richness < 0.8  -> "thin"    (implied cheap vs recent realized)
    else            -> "neutral"

Caveat encoded in the model: richness compares an *event* implied move
against a *quiet-period* realized baseline. A high reading before earnings
is often event premium, not mispricing -- the dashboard surfaces the
number, the trader supplies the judgment.
"""
from __future__ import annotations

import math

import numpy as np

from config import RICHNESS_RICH, RICHNESS_THIN, RV_LOOKBACK_DAYS, WIDE_SPREAD_PCT


def atm_straddle(calls, puts, spot: float) -> dict:
    common = sorted(set(calls["strike"]) & set(puts["strike"]))
    if not common:
        raise ValueError("no common strikes between calls and puts")
    strike = min(common, key=lambda k: abs(k - spot))
    c = calls[calls["strike"] == strike].iloc[0]
    p = puts[puts["strike"] == strike].iloc[0]
    c_mid = (float(c["bid"]) + float(c["ask"])) / 2.0
    p_mid = (float(p["bid"]) + float(p["ask"])) / 2.0
    return {
        "strike": float(strike),
        "call_mid": round(c_mid, 2),
        "put_mid": round(p_mid, 2),
        "straddle": round(c_mid + p_mid, 2),
        "legs": {
            "call_bid": float(c["bid"]), "call_ask": float(c["ask"]),
            "put_bid": float(p["bid"]), "put_ask": float(p["ask"]),
        },
    }


def quote_quality(legs: dict) -> str:
    """'wide' if any leg is missing or spread/mid is excessive."""
    for bid_key, ask_key in (("call_bid", "call_ask"), ("put_bid", "put_ask")):
        bid, ask = legs[bid_key], legs[ask_key]
        if bid <= 0 or ask <= 0:
            return "wide"
        mid = (bid + ask) / 2.0
        if mid > 0 and (ask - bid) / mid > WIDE_SPREAD_PCT:
            return "wide"
    return "tight"


def realized_move_pct(closes: list[float], dte: int,
                      lookback: int = RV_LOOKBACK_DAYS) -> float | None:
    """Recent realized volatility scaled to the option horizon.

    daily_std * sqrt(dte) -> expected % move over the holding period.
    """
    if len(closes) < lookback + 1 or dte <= 0:
        return None
    rets = np.log(np.array(closes[-(lookback + 1):]) /
                  np.array(closes[-(lookback + 2):-1]))
    daily_std = float(np.std(rets, ddof=1))
    return round(daily_std * math.sqrt(dte) * 100, 2)


def classify(richness: float | None) -> str:
    if richness is None:
        return "n/a"
    if richness > RICHNESS_RICH:
        return "rich"
    if richness < RICHNESS_THIN:
        return "thin"
    return "neutral"


def build_record(ticker: str, spot: float, expiry: str, dte: int,
                 earnings_date, earnings_estimated: bool,
                 straddle_info: dict, rv_pct: float | None) -> dict:
    straddle = straddle_info["straddle"]
    implied_pct = round(straddle / spot * 100, 2) if spot else None
    richness = (round(implied_pct / rv_pct, 4)
                if implied_pct and rv_pct else None)
    return {
        "ticker": ticker,
        "spot": round(spot, 2),
        "earnings_date": earnings_date.isoformat() if earnings_date else None,
        "earnings_estimated": earnings_estimated,
        "expiry": expiry,
        "dte": dte,
        "atm_strike": straddle_info["strike"],
        "straddle": straddle,
        "implied_move_pct": implied_pct,
        "realized_move_pct": rv_pct,
        "richness": richness,
        "verdict": classify(richness),
        "quote_quality": quote_quality(straddle_info["legs"]),
        "expected_low": round(spot - straddle, 2),
        "expected_high": round(spot + straddle, 2),
    }
