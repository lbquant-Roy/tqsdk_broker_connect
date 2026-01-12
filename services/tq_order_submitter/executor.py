"""
TqApi order execution logic
"""
import time
import pandas as pd
from typing import Dict, Any
from loguru import logger
from tqsdk import TqApi

import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')
from shared.constants import ORDER_EXPIRE_ALLOW_MAX

SESSION_END_BUFFER_SECONDS = 15


def is_in_trading_session(order_id):
    """Check if current time is within trading hours and not too close to session end."""
    now = pd.Timestamp.now(tz='Asia/Shanghai')
    current_time = now.time()

    sessions = [
        (pd.Timestamp('09:00:00').time(), pd.Timestamp('10:15:00').time()),
        (pd.Timestamp('10:30:00').time(), pd.Timestamp('11:30:00').time()),
        (pd.Timestamp('13:30:00').time(), pd.Timestamp('15:00:00').time())
    ]

    for start, end in sessions:
        if start <= current_time <= end:
            session_end_ts = pd.Timestamp.combine(now.date(), end).tz_localize('Asia/Shanghai')
            seconds_remaining = (session_end_ts - now).total_seconds()

            if seconds_remaining <= SESSION_END_BUFFER_SECONDS:
                logger.warning(f"Order {order_id} rejected - {seconds_remaining:.0f}s to session end")
                return False

            return True

    logger.warning(f"Order {order_id} rejected - not in trading session")
    return False


def check_order_age(order_request):
    """Validate order age to prevent stale orders."""
    order_id = order_request.get('order_id')
    timestamp = order_request.get('timestamp')

    if not timestamp:
        logger.warning(f"Order {order_id} rejected - missing timestamp")
        return False

    age = (time.time_ns() - timestamp) / 1e9

    if age > ORDER_EXPIRE_ALLOW_MAX:
        logger.warning(f"Order {order_id} rejected - {age:.3f}s old (max {ORDER_EXPIRE_ALLOW_MAX}s)")
        return False

    logger.debug(f"Order {order_id} age check passed: {age:.3f}s")
    return True


def execute_order(api: TqApi, db_writer, config, order_request: Dict[str, Any]) -> bool:
    """Execute order via TqApi after validation checks and DB insert."""
    try:
        # check first
        if not check_order_age(order_request):
            return False

        if not is_in_trading_session(order_request.get('order_id')):
            return False

        symbol = order_request['symbol']
        direction = order_request['direction']
        offset = order_request['offset']
        volume = order_request['volume']
        limit_price = order_request.get('limit_price', 0.0)
        order_id = order_request.get('order_id')
        portfolio_id = order_request.get('portfolio_id', config.portfolio_id)
        timestamp = order_request['timestamp']

        _print_price_str = f"{limit_price}" if limit_price else "MARKET"
        logger.info(f"Submitting order: {symbol} {direction} {offset} {volume} @ {_print_price_str}")

        # Prepare order data for DB insertion
        from shared.models import OrderHistoryFuturesChn
        order_data = OrderHistoryFuturesChn(
            order_id=order_id,
            instrument_id=symbol,  # Will be updated by monitor with TqSDK's instrument_id
            direction=direction,
            order_offset=offset,
            volume_orign=volume,
            volume_left=volume,
            limit_price=limit_price if limit_price else 0.0,
            qpto_portfolio_id=portfolio_id,
            qpto_contract_code=symbol,
            sender_type='tq_submitter',
            origin_timestamp=timestamp
        )

        # Insert to database BEFORE second validation
        if not db_writer.insert_order(order_data):
            logger.error(f"DB insert failed for order {order_id}, aborting submission")
            return False
        else:
            logger.info(f"DB insert success for order {order_id}")

        # before send, check again
        if not check_order_age(order_request):
            return False

        if not is_in_trading_session(order_request.get('order_id')):
            return False

        # Prepare TqSDK order params
        order_params = {
            'symbol': symbol,
            'direction': direction,
            'offset': offset,
            'volume': volume,
            'order_id': order_id
        }

        if limit_price:
            order_params['limit_price'] = limit_price

        api.wait_update()
        api.insert_order(**order_params)
        api.wait_update()

        logger.info(f"Order {order_id} submitted successfully")
        return True

    except Exception as e:
        logger.error(f"Order execution failed: {e}")
        return False
