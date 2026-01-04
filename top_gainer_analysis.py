#!/usr/bin/env python3
"""
Top Gainer Analysis: Momentum vs Mean Reversion
Analyzes what happens after a coin becomes a "top gainer"
"""

import pandas as pd
import numpy as np
import os
from collections import defaultdict

OHLCV_CACHE_DIR = "ohlcv_cache"
BERLIN_TZ = "Europe/Berlin"

# Symbols to analyze
SYMBOLS = [
    "BTC/USDC", "ETH/USDC", "SOL/USDC", "XRP/USDC", "LINK/USDC", "SUI/USDC",
    "BTC/EUR", "ETH/EUR", "SOL/EUR", "XRP/EUR", "LINK/EUR", "SUI/EUR",
]

# Thresholds for "top gainer" (24h return)
# Top gainers are typically published at 10%+ moves
GAINER_THRESHOLDS = [10, 15, 20, 25, 30]  # percent

# Forward looking periods (in hours)
FORWARD_PERIODS = [1, 4, 12, 24, 48]


def load_ohlcv(symbol, timeframe="1h"):
    """Load OHLCV data from cache."""
    safe_symbol = symbol.replace("/", "_")
    cache_file = os.path.join(OHLCV_CACHE_DIR, f"{safe_symbol}_{timeframe}.csv")

    if not os.path.exists(cache_file):
        return None

    df = pd.read_csv(cache_file, index_col=0, parse_dates=True)

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=True)

    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert(BERLIN_TZ)
    else:
        df.index = df.index.tz_convert(BERLIN_TZ)
    return df


def analyze_symbol(symbol, df):
    """Analyze top gainer patterns for a single symbol."""
    if df is None or len(df) < 100:
        return None

    results = {'bull': {}, 'bear': {}, 'all': {}}

    # Calculate 24h return (24 bars for 1h timeframe)
    df = df.copy()
    df['return_24h'] = df['close'].pct_change(24) * 100  # in percent

    # Detect market regime using 200-period SMA
    df['sma_200'] = df['close'].rolling(200).mean()
    df['is_bull'] = df['close'] > df['sma_200']

    for threshold in GAINER_THRESHOLDS:
        # Find all "top gainer" moments (>threshold% in 24h)
        gainer_mask = df['return_24h'] > threshold
        loser_mask = df['return_24h'] < -threshold

        # Split by market regime
        bull_gainer = df.index[gainer_mask & df['is_bull']]
        bear_gainer = df.index[gainer_mask & ~df['is_bull']]
        bull_loser = df.index[loser_mask & df['is_bull']]
        bear_loser = df.index[loser_mask & ~df['is_bull']]
        all_gainer = df.index[gainer_mask]
        all_loser = df.index[loser_mask]

        results['bull'][f'+{threshold}%'] = analyze_forward_returns(df, bull_gainer, f"Bull Gainer >{threshold}%")
        results['bull'][f'-{threshold}%'] = analyze_forward_returns(df, bull_loser, f"Bull Loser <-{threshold}%")
        results['bear'][f'+{threshold}%'] = analyze_forward_returns(df, bear_gainer, f"Bear Gainer >{threshold}%")
        results['bear'][f'-{threshold}%'] = analyze_forward_returns(df, bear_loser, f"Bear Loser <-{threshold}%")
        results['all'][f'+{threshold}%'] = analyze_forward_returns(df, all_gainer, f"All Gainer >{threshold}%")
        results['all'][f'-{threshold}%'] = analyze_forward_returns(df, all_loser, f"All Loser <-{threshold}%")

    return results


def analyze_forward_returns(df, signal_indices, label):
    """Analyze what happens after signal points."""
    if len(signal_indices) == 0:
        return None

    forward_returns = {period: [] for period in FORWARD_PERIODS}

    for idx in signal_indices:
        try:
            idx_pos = df.index.get_loc(idx)
            entry_price = df['close'].iloc[idx_pos]

            for period in FORWARD_PERIODS:
                if idx_pos + period < len(df):
                    future_price = df['close'].iloc[idx_pos + period]
                    ret = (future_price - entry_price) / entry_price * 100
                    forward_returns[period].append(ret)
        except:
            continue

    # Calculate statistics
    stats = {}
    for period in FORWARD_PERIODS:
        returns = forward_returns[period]
        if len(returns) > 10:
            returns = np.array(returns)
            stats[f'{period}h'] = {
                'count': len(returns),
                'mean': np.mean(returns),
                'median': np.median(returns),
                'std': np.std(returns),
                'win_rate': np.mean(returns > 0) * 100,
                'avg_win': np.mean(returns[returns > 0]) if np.any(returns > 0) else 0,
                'avg_loss': np.mean(returns[returns < 0]) if np.any(returns < 0) else 0,
            }

    return stats


def print_results(all_results):
    """Print analysis results."""

    for regime in ['bull', 'bear', 'all']:
        # Aggregate across all symbols for this regime
        aggregated = defaultdict(lambda: defaultdict(list))

        for symbol, symbol_results in all_results.items():
            if symbol_results is None:
                continue
            regime_results = symbol_results.get(regime, {})
            for threshold, stats in regime_results.items():
                if stats is None:
                    continue
                for period, period_stats in stats.items():
                    for key, value in period_stats.items():
                        aggregated[threshold][f'{period}_{key}'].append(value)

        regime_label = {"bull": "🐂 BULLENMARKT", "bear": "🐻 BÄRENMARKT", "all": "📊 GESAMT"}[regime]

        print("\n" + "=" * 80)
        print(f"  {regime_label} - TOP GAINER/LOSER ANALYSIS")
        print("=" * 80)

        for threshold in sorted(aggregated.keys(), key=lambda x: (x[0], abs(float(x[1:-1])))):
            print(f"\n  After {threshold} move in 24h:")
            print(f"  {'-'*50}")

            data = aggregated[threshold]

            for period in [24]:  # Focus on 24h forward
                count_key = f'{period}h_count'
                if count_key not in data or len(data[count_key]) == 0:
                    continue

                total_count = sum(data[count_key])
                avg_mean = np.mean(data[f'{period}h_mean'])
                avg_win_rate = np.mean(data[f'{period}h_win_rate'])

                # Interpretation
                if threshold.startswith('+'):
                    if avg_mean > 0.3:
                        signal = "→ MOMENTUM ↑ (weiter long)"
                    elif avg_mean < -0.3:
                        signal = "→ MEAN REVERSION ↓ (short)"
                    else:
                        signal = "→ NEUTRAL"
                else:
                    if avg_mean < -0.3:
                        signal = "→ MOMENTUM ↓ (weiter short)"
                    elif avg_mean > 0.3:
                        signal = "→ MEAN REVERSION ↑ (long)"
                    else:
                        signal = "→ NEUTRAL"

                print(f"    Next 24h: {avg_mean:+.2f}% avg, {avg_win_rate:.0f}% win rate (n={total_count}) {signal}")


def main():
    print("\n" + "=" * 80)
    print("  TOP GAINER/LOSER PATTERN ANALYSIS")
    print("  Question: After +X% in 24h, does the trend continue or reverse?")
    print("=" * 80)

    all_results = {}

    for symbol in SYMBOLS:
        df = load_ohlcv(symbol, "1h")
        if df is not None:
            print(f"Analyzing {symbol}: {len(df)} bars")
            all_results[symbol] = analyze_symbol(symbol, df)
        else:
            print(f"Skipping {symbol}: No data")

    print_results(all_results)

    # Summary recommendation
    print("\n" + "=" * 80)
    print("  TRADING IMPLICATIONS")
    print("=" * 80)
    print("""
  If MOMENTUM dominates (positive returns after big moves):
    → Trade WITH the trend
    → Buy top gainers, short top losers

  If MEAN REVERSION dominates (negative returns after big moves):
    → Trade AGAINST the trend
    → Short top gainers, buy top losers
    → Wait for exhaustion
    """)


if __name__ == "__main__":
    main()
