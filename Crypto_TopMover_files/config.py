"""
Crypto TopMover - Configuration
Trading strategy based on top gainers/losers mean reversion
"""

import os

# API Configuration
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY", "")
BINANCE_SECRET = os.environ.get("BINANCE_SECRET", "")

# Use testnet for paper trading
USE_TESTNET = True
TESTNET_API_KEY = os.environ.get("BINANCE_TESTNET_API_KEY", "")
TESTNET_SECRET = os.environ.get("BINANCE_TESTNET_SECRET", "")

# Timezone
BERLIN_TZ = "Europe/Berlin"

# Trading Parameters
INITIAL_CAPITAL = 10000.0  # USDT
POSITION_SIZE_PCT = 10.0   # % of capital per trade
MAX_POSITIONS = 5          # Maximum concurrent positions

# Signal Thresholds (based on analysis)
# Buy signal: coin dropped >10% in 24h (mean reversion)
BUY_THRESHOLD = -10.0      # Buy when 24h return < -10%

# Short signal: coin pumped >30% in 24h (mean reversion)
SHORT_THRESHOLD = 30.0     # Short when 24h return > +30%

# Market Regime Detection
SMA_PERIOD = 200           # Use 200-period SMA for bull/bear detection

# Risk Management
STOP_LOSS_PCT = 5.0        # Stop loss at -5%
TAKE_PROFIT_PCT = 8.0      # Take profit at +8% (based on avg win from analysis)
MAX_HOLD_HOURS = 48        # Maximum hold time

# Symbols to monitor
SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "LINK/USDT",
    "SUI/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "DOGE/USDT",
    "MATIC/USDT",
]

# Logging
LOG_DIR = "logs"
TRADE_LOG = os.path.join(LOG_DIR, "trades.csv")
SIGNAL_LOG = os.path.join(LOG_DIR, "signals.csv")

# Data Cache
CACHE_DIR = "ohlcv_cache"
