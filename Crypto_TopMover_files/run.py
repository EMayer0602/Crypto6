#!/usr/bin/env python3
"""
Crypto TopMover - Main Entry Point
"""

import argparse
from paper_trader import PaperTrader
from data_fetcher import scan_for_signals, fetch_24h_changes


def main():
    parser = argparse.ArgumentParser(description='Crypto TopMover Trading Bot')
    parser.add_argument('--scan', action='store_true', help='Scan for signals once')
    parser.add_argument('--trade', action='store_true', help='Run paper trader')
    parser.add_argument('--interval', type=int, default=60, help='Scan interval in minutes')

    args = parser.parse_args()

    if args.scan:
        # Just scan for signals
        print("=" * 60)
        print("  CRYPTO TOPMOVER - Signal Scanner")
        print("=" * 60)

        df = fetch_24h_changes()
        if not df.empty:
            print("\n24h Changes:")
            print(df[['symbol', 'change_24h', 'price', 'volume_24h']].to_string())

        print("\n")
        signals = scan_for_signals()

        if signals:
            print("\n" + "=" * 60)
            print("  TRADING SIGNALS")
            print("=" * 60)
            for s in signals:
                print(f"\n  {s['direction']} {s['symbol']}")
                print(f"    24h Change: {s['change_24h']:+.1f}%")
                print(f"    Price: ${s['price']:.4f}")
                print(f"    Regime: {s['regime']}")
                print(f"    Confidence: {s['confidence']:.0%}")
                print(f"    Reason: {s['reason']}")

    elif args.trade:
        # Run paper trader
        trader = PaperTrader()
        trader.run(interval_minutes=args.interval)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
