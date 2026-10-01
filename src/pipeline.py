"""Nightly pipeline run: refresh every ticker -> data/latest.json.

Usage:
    python src/pipeline.py                 # full watchlist
    TICKERS="SPY,MU" python src/pipeline.py  # quick test subset

Writes:
    data/latest.json            # consumed by app.py
    data/history/YYYY-MM-DD.json  # dated snapshot for trend analysis
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import ingest
import metrics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def refresh_ticker(ticker: str) -> dict:
    rec = {"ticker": ticker, "as_of": dt.date.today().isoformat(), "error": None}
    try:
        spot = ingest.get_spot(ticker)
        earn_date, earn_est = ingest.get_earnings_date(ticker)
        expiry = ingest.choose_expiry(ticker, earn_date)
        dte = (dt.date.fromisoformat(expiry) - dt.date.today()).days
        calls, puts = ingest.get_chain(ticker, expiry)
        straddle = metrics.atm_straddle(calls, puts, spot)
        closes = ingest.get_closes(ticker, config.RV_LOOKBACK_DAYS)
        rv = metrics.realized_move_pct(closes, dte)
        rec.update(metrics.build_record(
            ticker, spot, expiry, dte, earn_date, earn_est, straddle, rv))
    except Exception as exc:  # one bad ticker never kills the run
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


def main() -> None:
    tickers = os.environ.get("TICKERS")
    watch = [t.strip().upper() for t in tickers.split(",")] if tickers else config.WATCHLIST
    print(f"Refreshing {len(watch)} tickers...")
    records = [refresh_ticker(t) for t in watch]
    ok = [r for r in records if not r["error"]]
    bad = [r["ticker"] for r in records if r["error"]]
    payload = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
               "records": records}
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "latest.json"), "w") as f:
        json.dump(payload, f, indent=2)
    hist_dir = os.path.join(DATA, "history")
    os.makedirs(hist_dir, exist_ok=True)
    with open(os.path.join(hist_dir, f"{dt.date.today().isoformat()}.json"), "w") as f:
        json.dump(payload, f, indent=2)
    print(f"done: {len(ok)} ok, {len(bad)} failed")
    if bad:
        print("failed:", ", ".join(bad))
    for r in sorted(ok, key=lambda r: (r.get("richness") or 0), reverse=True)[:8]:
        print(f'  {r["ticker"]:5s} rich={r["richness"]} '
              f'impl={r["implied_move_pct"]}% rv={r["realized_move_pct"]}% '
              f'{r["expiry"]} ({r["quote_quality"]})')


if __name__ == "__main__":
    main()
