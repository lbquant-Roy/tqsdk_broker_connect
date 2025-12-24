"""
Loop-based position monitoring for reconciliation and universe tracking.
Runs every 5 seconds, compares TqApi positions with Redis.
"""
import sys
import time

sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from loguru import logger
from tqsdk import TqApi

from shared.redis_client import RedisClient
from shared.models import FullPosition
from shared.product_universe import ProductUniverseLoader
from shared.constants import POSITION_LOOP_INTERVAL_SECONDS


class PositionLoopMonitor:
    """Loop-based reconciliation monitor with universe tracking"""

    def __init__(self, api: TqApi, portfolio_id: str, redis_client: RedisClient,
                 universe_loader: ProductUniverseLoader):
        self.api = api
        self.portfolio_id = portfolio_id
        self.redis = redis_client
        self.universe_loader = universe_loader
        self.running = False
        self.loop_interval = POSITION_LOOP_INTERVAL_SECONDS
        self.last_success_ts = 0

    def start(self):
        """Start the reconciliation loop"""
        self.running = True
        logger.info(f"Position loop monitor started (interval={self.loop_interval}s)")

        while self.running:
            try:
                self.api.wait_update()

                current_time = time.time()
                ts_gap = current_time - self.last_success_ts

                if ts_gap >= self.loop_interval:
                    logger.info(f"Start Reconciliation Cycle (elapsed={ts_gap:.1f}s)")
                    self._reconciliation_cycle()
                    self.last_success_ts = current_time
                    logger.info(f"Finish Reconciliation Cycle")
                else:
                    logger.debug(f"Skip cycle (only {ts_gap:.1f}s elapsed, need {self.loop_interval}s)")
            except Exception as e:
                if self.running:
                    logger.error(f"Error in loop monitor: {e}")
                    time.sleep(1)

    def stop(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Position loop monitor stopping...")

    def _reconciliation_cycle(self):
        """Single reconciliation cycle"""

        # Get universe symbols (main + next contracts)
        universe_symbols = self.universe_loader.load_universe()

        # Track which symbols we've processed
        processed_symbols = set()

        # Get current positions from TqApi
        tq_positions = self.api.get_position()

        # Process all TqApi positions
        for symbol, pos in tq_positions.items():
            tq_position = FullPosition.from_tqsdk_position(pos)
            self._reconcile_position(symbol, tq_position)
            processed_symbols.add(symbol)

        # Ensure universe symbols exist (initialize with zero if not in TqApi)
        for symbol in universe_symbols:
            if symbol not in processed_symbols:
                self._ensure_position_exists(symbol)

    def _reconcile_position(self, symbol: str, tq_position: FullPosition):
        """Reconcile a single position with Redis"""
        redis_position = self.redis.get_full_position(self.portfolio_id, symbol)

        if redis_position is None:
            # Not in Redis - set it
            self.redis.set_full_position(self.portfolio_id, symbol, tq_position)
            logger.info(f"Initialized position: {symbol} pos={tq_position.pos}")
        elif tq_position.equals(redis_position):
            # Same - just refresh TTL
            self.redis.refresh_position_ttl(self.portfolio_id, symbol)
            logger.info(f"Position TTL refreshed: {symbol}")
        else:
            # Mismatch - log warning, update with TqApi value (source of truth)
            logger.warning(f"Position mismatch for {symbol}: "
                           f"TqApi={tq_position.pos}, Redis={redis_position.pos}")
            self.redis.set_full_position(self.portfolio_id, symbol, tq_position)

    def _ensure_position_exists(self, symbol: str):
        """Ensure a universe symbol has a position entry (zero if not held)"""
        redis_position = self.redis.get_full_position(self.portfolio_id, symbol)

        if redis_position is None:
            # Initialize with zero position
            self.redis.set_full_position(self.portfolio_id, symbol, FullPosition.zero())
            logger.info(f"Initialized zero position for universe symbol: {symbol}")
        else:
            # Exists - just refresh TTL
            self.redis.refresh_position_ttl(self.portfolio_id, symbol)
