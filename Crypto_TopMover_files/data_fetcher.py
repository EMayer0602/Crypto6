"""
Crypto TopMover - Data Fetcher
Fetches top gainers/losers from Binance
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

from config import (
    BINANCE_API_KEY, BINANCE_SECRET,
    TESTNET_API_KEY, TESTNET_SECRET,
    USE_TESTNET, BERLIN_TZ, SYMBOLS, CACHE_DIR
)


def get_exchange():
    """Get Binance exchange instance."""
    if USE_TESTNET:
        exchange = ccxt.binance({
            'apiKey': TESTNET_API_KEY,
            'secret': TESTNET_SECRET,
            'sandbox': True,
            'options': {'defaultType': 'spot'}
        })
    else:
        exchange = ccxt.binance({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_SECRET,
            'options': {'defaultType': 'spot'}
        })
    return exchange


def fetch_24h_changes():
    """
    Fetch 24h price changes for all symbols.
    Returns DataFrame with symbol, price, change_24h, volume
    """
    exchange = get_exchange()

    try:
        tickers = exchange.fetch_tickers(SYMBOLS)
    except Exception as e:
        print(f"Error fetching tickers: {e}")
        return pd.DataFrame()

    data = []
    for symbol, ticker in tickers.items():
        data.append({
            'symbol': symbol,
            'price': ticker.get('last', 0),
            'change_24h': ticker.get('percentage', 0),
            'volume_24h': ticker.get('quoteVolume', 0),
            'high_24h': ticker.get('high', 0),
            'low_24h': ticker.get('low', 0),
            'timestamp': datetime.now()
        })

    df = pd.DataFrame(data)
    df = df.sort_values('change_24h', ascending=False)
    return df


def get_top_gainers(df, threshold=10.0):
    """Get symbols with >threshold% gain in 24h."""
    return df[df['change_24h'] >= threshold]


def get_top_losers(df, threshold=-10.0):
    """Get symbols with <threshold% loss in 24h."""
    return df[df['change_24h'] <= threshold]


def fetch_ohlcv(symbol, timeframe='1h', limit=200):
    """Fetch OHLCV data for a symbol."""
    exchange = get_exchange()

    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df = df.set_index('timestamp')
        df.index = df.index.tz_convert(BERLIN_TZ)
        return df
    except Exception as e:
        print(f"Error fetching OHLCV for {symbol}: {e}")
        return pd.DataFrame()


def detect_market_regime(df, sma_period=200):
    """
    Detect if we're in bull or bear market.
    Bull: price > SMA200
    Bear: price < SMA200
    """
    if len(df) < sma_period:
        return "unknown"

    sma = df['close'].rolling(sma_period).mean()
    current_price = df['close'].iloc[-1]
    current_sma = sma.iloc[-1]

    if pd.isna(current_sma):
        return "unknown"

    return "bull" if current_price > current_sma else "bear"


def scan_for_signals():
    """
    Scan all symbols for trading signals.
    Returns list of signals with symbol, direction, and confidence.
    """
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scanning for signals...")

    df = fetch_24h_changes()
    if df.empty:
        print("No data fetched")
        return []

    signals = []

    # Check for buy signals (top losers for mean reversion)
    losers = get_top_losers(df, threshold=-10.0)
    for _, row in losers.iterrows():
        # Get more data to check market regime
        ohlcv = fetch_ohlcv(row['symbol'], '1h', 250)
        regime = detect_market_regime(ohlcv) if not ohlcv.empty else "unknown"

        # Stronger signal in bear market (based on analysis: 79% win rate)
        confidence = 0.79 if regime == "bear" else 0.65

        signals.append({
            'symbol': row['symbol'],
            'direction': 'LONG',
            'change_24h': row['change_24h'],
            'price': row['price'],
            'regime': regime,
            'confidence': confidence,
            'reason': f"Mean reversion: {row['change_24h']:.1f}% drop in 24h"
        })

    # Check for short signals (top gainers >30% for mean reversion)
    gainers = get_top_gainers(df, threshold=30.0)
    for _, row in gainers.iterrows():
        ohlcv = fetch_ohlcv(row['symbol'], '1h', 250)
        regime = detect_market_regime(ohlcv) if not ohlcv.empty else "unknown"

        # Based on analysis: +30% gainers tend to drop -2.79% next 24h
        confidence = 0.55 if regime == "bull" else 0.50

        signals.append({
            'symbol': row['symbol'],
            'direction': 'SHORT',
            'change_24h': row['change_24h'],
            'price': row['price'],
            'regime': regime,
            'confidence': confidence,
            'reason': f"Mean reversion: +{row['change_24h']:.1f}% pump in 24h"
        })

    # Sort by confidence
    signals = sorted(signals, key=lambda x: x['confidence'], reverse=True)

    print(f"Found {len(signals)} signals")
    for sig in signals:
        print(f"  {sig['direction']} {sig['symbol']}: {sig['change_24h']:+.1f}% "
              f"(regime: {sig['regime']}, confidence: {sig['confidence']:.0%})")

    return signals


if __name__ == "__main__":
    # Test the scanner
    print("=" * 60)
    print("  CRYPTO TOPMOVER - Market Scanner")
    print("=" * 60)

    # Fetch current 24h changes
    df = fetch_24h_changes()
    if not df.empty:
        print("\nTop Gainers:")
        print(df.head(5)[['symbol', 'change_24h', 'price']].to_string())

        print("\nTop Losers:")
        print(df.tail(5)[['symbol', 'change_24h', 'price']].to_string())

    # Scan for signals
    signals = scan_for_signals()
