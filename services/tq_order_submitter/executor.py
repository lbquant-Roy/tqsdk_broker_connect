"""
TqApi order execution logic
"""
from typing import Dict, Any, Optional
from loguru import logger
from tqsdk import TqApi


def execute_order(api: TqApi, order_request: Dict[str, Any]) -> bool:
    """
    Execute a single order via TqApi

    Returns True if order submitted successfully, False otherwise
    """
    try:
        symbol = order_request['symbol']
        direction = order_request['direction']
        offset = order_request['offset']
        volume = order_request['volume']
        limit_price = order_request.get('limit_price')
        order_id = order_request.get('order_id')

        logger.info(f"Executing order: {symbol} {direction} {offset} {volume} @ {limit_price or 'MARKET'}")

        if limit_price:
            order = api.insert_order(
                symbol=symbol,
                direction=direction,
                offset=offset,
                volume=volume,
                limit_price=limit_price,
                order_id=order_id
            )
        else:
            order = api.insert_order(
                symbol=symbol,
                direction=direction,
                offset=offset,
                volume=volume,
                order_id=order_id
            )

        # Send the order to the server (insert_order only queues it)
        # wait_update() flushes queued messages and processes responses
        api.wait_update()

        logger.info(f"Order submitted: {order.order_id} status={order.status}")
        return True

    except Exception as e:
        logger.error(f"Failed to execute order: {e}")
        return False
