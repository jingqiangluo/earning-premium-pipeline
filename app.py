"""Streamlit dashboard: earnings-season premium richness board.

Run:  streamlit run app.py
Reads data/latest.json produced by src/pipeline.py.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import streamlit as st

st.set_page_config(page_title="Earning Season Premium", layout="wide")
st.title("Earning Season Premium 定价看板")

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "latest.json")

try:
    with open(DATA_PATH) as f:
        payload = json.load(f)
except FileNotFoundError:
    st.warning("No data yet — run `python src/pipeline.py` first.")
    st.stop()

st.caption(f"Generated at {payload['generated_at']} (delayed quotes, for reference only)")

records = [r for r in payload["records"] if not r.get("error")]
failed = [r["ticker"] for r in payload["records"] if r.get("error")]
if failed:
    st.warning(f"No usable data: {', '.join(failed)}")

records.sort(key=lambda r: (r.get("richness") or 0), reverse=True)

BADGE = {"rich": "🔴", "thin": "🟢", "neutral": "⚪", "n/a": "⬜"}

cols = st.columns([1, 1, 1, 1, 1, 1, 1, 1])
for c, h in zip(cols, ["Ticker", "Spot", "Expiry", "ATM Straddle",
                       "Implied", "Realized", "Richness", "Quote"]):
    c.markdown(f"**{h}**")

for r in records:
    cols = st.columns([1, 1, 1, 1, 1, 1, 1, 1])
    earn = f" ({r['earnings_date']}{'~' if r['earnings_estimated'] else ''})" \
        if r.get("earnings_date") else ""
    vals = [
        f"{BADGE.get(r['verdict'], '')} **{r['ticker']}**",
        f"${r['spot']}",
        f"{r['expiry']}{earn}",
        f"${r['straddle']} @ {r['atm_strike']:.0f}",
        f"{r['implied_move_pct']}%",
        f"{r['realized_move_pct']}%" if r["realized_move_pct"] else "n/a",
        f"{r['richness']}×" if r["richness"] else "n/a",
        r["quote_quality"],
    ]
    for c, v in zip(cols, vals):
        c.markdown(v)
    with st.expander(f"{r['ticker']} detail"):
        st.write(f"Expected range: ${r['expected_low']} – ${r['expected_high']} "
                 f"(±{r['implied_move_pct']}%)")
        st.write(f"Earnings: {r['earnings_date'] or 'n/a'} "
                 f"{'(estimated)' if r['earnings_estimated'] else ''} · "
                 f"DTE {r['dte']}")

st.caption("~ = estimated earnings date. Verify with the company calendar before trading. "
           "Broker prices are authoritative; this board is a delayed reference.")
