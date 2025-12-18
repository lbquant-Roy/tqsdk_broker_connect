"""
Position monitoring logic using TqApi wait_update()
"""
from typing import Dict, Any, Callable
from loguru import logger
from tqsdk import TqApi

import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from shared.redis_client import RedisClient


class PositionMonitor:
    """Monitor position changes from TqApi"""

    def __init__(self, api: TqApi, portfolio_id: str, redis_client: RedisClient):
        self.api = api
        self.portfolio_id = portfolio_id
        self.redis_client = redis_client
        self.previous_positions: Dict[str, float] = {}
        self.running = False

    def start(self, on_update: Callable[[Dict[str, Any]], None]):
        """Start monitoring position changes"""
        self.running = True
        logger.info("Position monitor started")

        while self.running:
            try:
                self.api.wait_update()
                self._check_position_updates(on_update)
            except Exception as e:
                if self.running:
                    logger.error(f"Error in position monitor loop: {e}")

    def stop(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Position monitor stopping...")

    def _check_position_updates(self, on_update: Callable[[Dict[str, Any]], None]):
        """Check for position changes and publish updates"""
        positions = self.api.get_position()
        current_positions: Dict[str, float] = {}

        for symbol, pos in positions.items():
            net_pos = pos.pos_long - pos.pos_short
            current_positions[symbol] = net_pos

            # Check if position changed
            prev_pos = self.previous_positions.get(symbol, 0)
            if net_pos != prev_pos:
                # Build breakdown for CLOSETODAY handling
                breakdown = {
                    'pos_long_today': pos.pos_long_today,
                    'pos_long_his': pos.pos_long_his,
                    'pos_short_today': pos.pos_short_today,
                    'pos_short_his': pos.pos_short_his
                }

                # Cache breakdown to Redis
                self.redis_client.set_position_breakdown(
                    self.portfolio_id, symbol, breakdown
                )

                update = {
                    'type': 'POSITION_UPDATE',
                    'portfolio_id': self.portfolio_id,
                    'symbol': symbol,
                    'net_position': net_pos,
                    'breakdown': breakdown
                }

                logger.info(f"Position update: {symbol} {prev_pos} -> {net_pos}")
                on_update(update)

        # Check for positions that became zero
        for symbol in list(self.previous_positions.keys()):
            if symbol not in current_positions or current_positions[symbol] == 0:
                if self.previous_positions.get(symbol, 0) != 0:
                    update = {
                        'type': 'POSITION_UPDATE',
                        'portfolio_id': self.portfolio_id,
                        'symbol': symbol,
                        'net_position': 0,
                        'breakdown': {
                            'pos_long_today': 0,
                            'pos_long_his': 0,
                            'pos_short_today': 0,
                            'pos_short_his': 0
                        }
                    }
                    logger.info(f"Position closed: {symbol}")
                    on_update(update)

        self.previous_positions = current_positions
