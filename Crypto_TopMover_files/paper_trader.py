"""
Crypto TopMover - Paper Trader
Simulates trades based on top mover signals
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import time
import json

from config import (
    INITIAL_CAPITAL, POSITION_SIZE_PCT, MAX_POSITIONS,
    BUY_THRESHOLD, SHORT_THRESHOLD,
    STOP_LOSS_PCT, TAKE_PROFIT_PCT, MAX_HOLD_HOURS,
    LOG_DIR, TRADE_LOG, SIGNAL_LOG, BERLIN_TZ
)
from data_fetcher import scan_for_signals, fetch_24h_changes, fetch_ohlcv


class PaperTrader:
    def __init__(self):
        self.capital = INITIAL_CAPITAL
        self.positions = {}  # symbol -> position info
        self.trade_history = []
        self.signal_history = []

        # Create log directory
        os.makedirs(LOG_DIR, exist_ok=True)

        # Load existing state if available
        self.load_state()

    def load_state(self):
        """Load previous state from disk."""
        state_file = os.path.join(LOG_DIR, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    self.capital = state.get('capital', INITIAL_CAPITAL)
                    self.positions = state.get('positions', {})
                    print(f"Loaded state: Capital={self.capital:.2f}, Positions={len(self.positions)}")
            except:
                pass

    def save_state(self):
        """Save current state to disk."""
        state_file = os.path.join(LOG_DIR, "state.json")
        state = {
            'capital': self.capital,
            'positions': self.positions,
            'last_update': datetime.now().isoformat()
        }
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def get_position_size(self):
        """Calculate position size based on capital."""
        return self.capital * (POSITION_SIZE_PCT / 100)

    def can_open_position(self):
        """Check if we can open a new position."""
        return len(self.positions) < MAX_POSITIONS

    def open_position(self, signal):
        """Open a new position based on signal."""
        symbol = signal['symbol']

        if symbol in self.positions:
            print(f"  Already have position in {symbol}")
            return False

        if not self.can_open_position():
            print(f"  Max positions ({MAX_POSITIONS}) reached")
            return False

        size = self.get_position_size()
        entry_price = signal['price']
        direction = signal['direction']

        # Calculate stop loss and take profit
        if direction == 'LONG':
            stop_loss = entry_price * (1 - STOP_LOSS_PCT / 100)
            take_profit = entry_price * (1 + TAKE_PROFIT_PCT / 100)
        else:  # SHORT
            stop_loss = entry_price * (1 + STOP_LOSS_PCT / 100)
            take_profit = entry_price * (1 - TAKE_PROFIT_PCT / 100)

        position = {
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'size_usd': size,
            'quantity': size / entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_time': datetime.now().isoformat(),
            'reason': signal['reason'],
            'confidence': signal['confidence'],
            'regime': signal['regime']
        }

        self.positions[symbol] = position
        self.capital -= size  # Reserve capital

        print(f"  OPENED {direction} {symbol} @ {entry_price:.4f}")
        print(f"    Size: ${size:.2f}, SL: {stop_loss:.4f}, TP: {take_profit:.4f}")

        self.save_state()
        self.log_trade('OPEN', position)
        return True

    def check_position(self, symbol, current_price):
        """Check if position should be closed."""
        if symbol not in self.positions:
            return None

        pos = self.positions[symbol]
        entry_price = pos['entry_price']
        direction = pos['direction']

        # Calculate P&L
        if direction == 'LONG':
            pnl_pct = (current_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - current_price) / entry_price * 100

        # Check stop loss
        if direction == 'LONG' and current_price <= pos['stop_loss']:
            return ('STOP_LOSS', pnl_pct)
        if direction == 'SHORT' and current_price >= pos['stop_loss']:
            return ('STOP_LOSS', pnl_pct)

        # Check take profit
        if direction == 'LONG' and current_price >= pos['take_profit']:
            return ('TAKE_PROFIT', pnl_pct)
        if direction == 'SHORT' and current_price <= pos['take_profit']:
            return ('TAKE_PROFIT', pnl_pct)

        # Check max hold time
        entry_time = datetime.fromisoformat(pos['entry_time'])
        hold_hours = (datetime.now() - entry_time).total_seconds() / 3600
        if hold_hours >= MAX_HOLD_HOURS:
            return ('MAX_HOLD', pnl_pct)

        return None

    def close_position(self, symbol, current_price, reason):
        """Close a position."""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        entry_price = pos['entry_price']
        direction = pos['direction']
        size_usd = pos['size_usd']

        # Calculate P&L
        if direction == 'LONG':
            pnl_pct = (current_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - current_price) / entry_price * 100

        pnl_usd = size_usd * (pnl_pct / 100)

        # Update capital
        self.capital += size_usd + pnl_usd

        print(f"  CLOSED {direction} {symbol} @ {current_price:.4f}")
        print(f"    Reason: {reason}, P&L: {pnl_pct:+.2f}% (${pnl_usd:+.2f})")

        # Log trade
        pos['exit_price'] = current_price
        pos['exit_time'] = datetime.now().isoformat()
        pos['exit_reason'] = reason
        pos['pnl_pct'] = pnl_pct
        pos['pnl_usd'] = pnl_usd
        self.log_trade('CLOSE', pos)

        # Add to history
        self.trade_history.append(pos)

        # Remove position
        del self.positions[symbol]
        self.save_state()

    def log_trade(self, action, position):
        """Log trade to CSV."""
        trade_data = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            **position
        }

        df = pd.DataFrame([trade_data])

        if os.path.exists(TRADE_LOG):
            df.to_csv(TRADE_LOG, mode='a', header=False, index=False)
        else:
            df.to_csv(TRADE_LOG, index=False)

    def update_positions(self):
        """Update all open positions with current prices."""
        if not self.positions:
            return

        print("\nChecking open positions...")
        df = fetch_24h_changes()

        for symbol in list(self.positions.keys()):
            row = df[df['symbol'] == symbol]
            if row.empty:
                continue

            current_price = row.iloc[0]['price']
            result = self.check_position(symbol, current_price)

            if result:
                reason, pnl = result
                self.close_position(symbol, current_price, reason)

    def process_signals(self, signals):
        """Process new signals and open positions."""
        print("\nProcessing signals...")

        for signal in signals:
            # Only take high confidence signals
            if signal['confidence'] >= 0.65:
                self.open_position(signal)

    def print_status(self):
        """Print current portfolio status."""
        print("\n" + "=" * 60)
        print("  PORTFOLIO STATUS")
        print("=" * 60)
        print(f"  Capital: ${self.capital:.2f}")
        print(f"  Open Positions: {len(self.positions)}")

        if self.positions:
            print("\n  Positions:")
            for symbol, pos in self.positions.items():
                print(f"    {pos['direction']} {symbol}: Entry ${pos['entry_price']:.4f}, "
                      f"Size ${pos['size_usd']:.2f}")

        # Calculate total P&L from history
        if self.trade_history:
            total_pnl = sum(t.get('pnl_usd', 0) for t in self.trade_history)
            wins = sum(1 for t in self.trade_history if t.get('pnl_usd', 0) > 0)
            total = len(self.trade_history)
            win_rate = wins / total * 100 if total > 0 else 0

            print(f"\n  Trade History:")
            print(f"    Total Trades: {total}")
            print(f"    Win Rate: {win_rate:.1f}%")
            print(f"    Total P&L: ${total_pnl:+.2f}")

    def run(self, interval_minutes=60):
        """Run the paper trader in a loop."""
        print("\n" + "=" * 60)
        print("  CRYPTO TOPMOVER - Paper Trader")
        print("  Strategy: Buy losers (-10%), Short gainers (+30%)")
        print("=" * 60)

        self.print_status()

        while True:
            try:
                # Update existing positions
                self.update_positions()

                # Scan for new signals
                signals = scan_for_signals()

                # Process signals
                if signals:
                    self.process_signals(signals)

                # Print status
                self.print_status()

                # Wait for next interval
                print(f"\nNext scan in {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)

            except KeyboardInterrupt:
                print("\nStopping paper trader...")
                self.save_state()
                break
            except Exception as e:
                print(f"\nError: {e}")
                time.sleep(60)


def main():
    trader = PaperTrader()
    trader.run(interval_minutes=60)


if __name__ == "__main__":
    main()
