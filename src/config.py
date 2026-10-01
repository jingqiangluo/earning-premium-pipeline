"""Shared configuration for the earnings-premium pipeline."""

# Core watchlist: high-option-volume names around earnings season.
# Override at runtime for testing:  TICKERS="SPY,MU" python src/pipeline.py
WATCHLIST = [
    "CRWV", "AVGO", "VST", "APP", "DDOG", "ON", "ORCL", "UMAC",
    "INTC", "MU", "AMD", "TEM", "HOOD", "BE", "OKLO", "DELL",
    "SPY", "CRCL",
]

# Richness = implied_move / realized_move (same horizon)
RICHNESS_RICH = 1.2   # premium looks rich  (>1.2x)
RICHNESS_THIN = 0.8   # premium looks thin  (<0.8x)

# Realized-volatility lookback, in trading days
RV_LOOKBACK_DAYS = 30

# A quote is "wide" if any of the 4 legs (call/put bid/ask) is missing,
# or if spread/mid exceeds this fraction on any leg.
WIDE_SPREAD_PCT = 0.10
