"""
Redis writer for position updates
"""
from typing import Dict, Any
from loguru import logger

import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from shared.redis_client import RedisClient


class PositionRedisWriter:
    """Writer for position updates to Redis"""

    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client

    def write_position_update(self, update: Dict[str, Any]) -> bool:
        """Write position update to Redis"""
        try:
            portfolio_id = update.get('portfolio_id')
            symbol = update.get('symbol')
            net_position = update.get('net_position', 0)

            self.redis_client.set_position(portfolio_id, symbol, net_position)
            logger.debug(f"Position written: {symbol} = {net_position}")
            return True

        except Exception as e:
            logger.error(f"Failed to write position: {e}")
            return False
