"""
Event-driven position monitoring using TqApi wait_update().
Writes directly to Redis on each position change.
"""
import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from typing import Dict
from loguru import logger
from tqsdk import TqApi

from shared.redis_client import RedisClient
from shared.models import FullPosition


class PositionUpdateMonitor:
    """Event-driven monitor that writes position updates directly to Redis"""

    def __init__(self, api: TqApi, portfolio_id: str, redis_client: RedisClient):
        self.api = api
        self.portfolio_id = portfolio_id
        self.redis = redis_client
        self.previous_positions: Dict[str, FullPosition] = {}
        self.running = False

    def start(self):
        """Start event-driven monitoring loop"""
        self.running = True
        logger.info("Position update monitor started")

        while self.running:
            try:
                self.api.wait_update()
                self._process_position_updates()
            except Exception as e:
                if self.running:
                    logger.error(f"Error in monitor loop: {e}")

    def stop(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Position update monitor stopping...")

    def _process_position_updates(self):
        """Check and write any position changes to Redis"""
        positions = self.api.get_position()
        current_symbols = set()

        for symbol, pos in positions.items():
            current_symbols.add(symbol)
            current = FullPosition.from_tqsdk_position(pos)
            previous = self.previous_positions.get(symbol)

            # Write if changed (force update)
            if previous is None or not current.equals(previous):
                self.redis.set_full_position(self.portfolio_id, symbol, current)
                if previous is None:
                    logger.info(f"Position init: {symbol} pos={current.pos}")
                else:
                    logger.info(f"Position update: {symbol} pos={previous.pos} -> {current.pos}")
                self.previous_positions[symbol] = current

        # Handle closed positions (went to zero or disappeared)
        for symbol in list(self.previous_positions.keys()):
            if symbol not in current_symbols:
                zero_pos = FullPosition.zero()
                self.redis.set_full_position(self.portfolio_id, symbol, zero_pos)
                logger.info(f"Position closed: {symbol}")
                del self.previous_positions[symbol]
