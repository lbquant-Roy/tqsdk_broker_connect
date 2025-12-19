"""
CLOSETODAY order splitting logic for SHFE/INE exchanges
"""
from typing import List, Dict, Any, Optional
from loguru import logger

import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from shared.constants import CLOSETODAY_EXCHANGES
from shared.redis_client import RedisClient


def requires_closetoday(symbol: str) -> bool:
    """Check if symbol requires CLOSETODAY handling"""
    exchange = symbol.split('.')[0] if '.' in symbol else ''
    return exchange in CLOSETODAY_EXCHANGES


def split_close_order(
    order_request: Dict[str, Any],
    redis_client: RedisClient,
    portfolio_id: str
) -> List[Dict[str, Any]]:
    """
    Split CLOSE orders for SHFE/INE into CLOSETODAY + CLOSE

    Returns list of order requests (1 if no split needed, 2 if split)
    """
    symbol = order_request.get('symbol', '')
    offset = order_request.get('offset', '')

    # Only split CLOSE orders for SHFE/INE
    if offset != 'CLOSE' or not requires_closetoday(symbol):
        return [order_request]

    # Get full position from Redis
    position = redis_client.get_full_position(portfolio_id, symbol)
    if not position:
        logger.warning(f"No position found for {symbol}, using original CLOSE")
        return [order_request]

    direction = order_request.get('direction', '')
    volume = order_request.get('volume', 0)
    base_order_id = order_request.get('order_id', '')

    # Determine which positions to close based on direction
    if direction == 'SELL':  # Closing long positions
        today_qty = position.pos_long_today
        his_qty = position.pos_long_his
    else:  # BUY - Closing short positions
        today_qty = position.pos_short_today
        his_qty = position.pos_short_his

    orders = []
    remaining = volume

    # CLOSETODAY first (close today's positions)
    if today_qty > 0 and remaining > 0:
        closetoday_vol = min(today_qty, remaining)
        closetoday_order = order_request.copy()
        closetoday_order['offset'] = 'CLOSETODAY'
        closetoday_order['volume'] = closetoday_vol
        closetoday_order['order_id'] = f"{base_order_id}_closetoday"
        orders.append(closetoday_order)
        remaining -= closetoday_vol
        logger.info(f"Split CLOSETODAY order: {symbol} {direction} {closetoday_vol}")

    # Then CLOSE for historical positions
    if his_qty > 0 and remaining > 0:
        close_vol = min(his_qty, remaining)
        close_order = order_request.copy()
        close_order['offset'] = 'CLOSE'
        close_order['volume'] = close_vol
        close_order['order_id'] = f"{base_order_id}_close"
        orders.append(close_order)
        logger.info(f"Split CLOSE order: {symbol} {direction} {close_vol}")

    if not orders:
        logger.warning(f"No positions to close for {symbol}, returning original order")
        return [order_request]

    return orders
