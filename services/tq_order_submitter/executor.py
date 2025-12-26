"""
TqApi order execution logic
"""
import time
from datetime import datetime
from typing import Dict, Any
from loguru import logger
from tqsdk import TqApi

import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')
from shared.constants import ORDER_EXPIRE_ALLOW_MAX

# Trading session end buffer in seconds
SESSION_END_BUFFER_SECONDS = 15


def is_in_trading_session(order_id):
    """
    Check if current time is within trading hours and not in the last 15 seconds of a session.

    Trading sessions:
    - 09:00:00 - 10:15:00 (morning session 1)
    - 10:30:00 - 11:30:00 (morning session 2)
    - 13:30:00 - 15:00:00 (afternoon session)

    Returns:
        bool: True if valid trading time, False otherwise
    """
    try:
        import pytz
        tz = pytz.timezone("Asia/Shanghai")
        now = datetime.now(tz)
    except ImportError:
        from datetime import timezone, timedelta
        tz = timezone(timedelta(hours=8))
        now = datetime.now(tz)

    hour = now.hour
    minute = now.minute
    second = now.second
    time_in_seconds = hour * 3600 + minute * 60 + second

    # Trading sessions in seconds from midnight (start, end)
    sessions = [
        (9 * 3600, 10 * 3600 + 15 * 60),
        (10 * 3600 + 30 * 60, 11 * 3600 + 30 * 60),
        (13 * 3600 + 30 * 60, 15 * 3600)
    ]

    # Check if in any trading session
    in_session = False
    current_session_end = None

    for session_start, session_end in sessions:
        if session_start <= time_in_seconds <= session_end:
            in_session = True
            current_session_end = session_end
            break

    if not in_session:
        logger.warning(f"Order rejected: {order_id} - Not in trading session")
        return False

    # Check if within last 15 seconds of session
    time_to_session_end = current_session_end - time_in_seconds
    if time_to_session_end <= SESSION_END_BUFFER_SECONDS:
        logger.warning(
            f"Order rejected: {order_id} - Too close to session end "
            f"({time_to_session_end}s remaining)"
        )
        return False

    return True


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

        # Check order expiration
        order_timestamp = order_request.get('timestamp', None)
        if order_timestamp:
            current_time_ns = time.time_ns()
            age_seconds = (current_time_ns - order_timestamp) / 1e9

            if age_seconds > ORDER_EXPIRE_ALLOW_MAX:
                logger.warning(
                    f"Order expired: {order_id} age={age_seconds:.3f}s "
                    f"exceeds max={ORDER_EXPIRE_ALLOW_MAX}s, rejecting order"
                )
                return False

            logger.debug(f"Order age check passed: {order_id} age={age_seconds:.3f}s")
        else:
            # if not has vaild timestamp, this order should also failed.
            logger.warning(f"Order rejected: {order_id} missing timestamp field")
            return False
        
        # Check trading session
        if not is_in_trading_session(order_id):
            return False

        logger.info(f"Executing order: {symbol} {direction} {offset} {volume} @ {limit_price or 'MARKET'}")

        api.wait_update()

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
            
        api.wait_update()
        # # Keep waiting for the order to leave ALIVE so we know the exchange response
        # while True:
        #     api.wait_update()

        #     if api.is_changing(order, ["status", "last_msg", "volume_left"]):
        #         filled = order.volume_orign - order.volume_left
        #         logger.info(
        #             f"Order update: {order.order_id} status={order.status} "
        #             f"filled={filled} last_msg={order.last_msg}"
        #         )

        #     if order.status != "ALIVE":
        #         break

        # if order.status != "FINISHED":
        #     logger.error(
        #         f"Order failed: {order.order_id} status={order.status} "
        #         f"last_msg={order.last_msg or 'unknown'}"
        #     )
        #     return False

        # logger.info(f"Order completed: {order.order_id} status={order.status}")
        # return True

    except Exception as e:
        logger.error(f"Failed to execute order: {e}")
        return False
