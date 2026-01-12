"""
Order submission worker logic
Runs in worker thread, processes messages with validation
"""
import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from loguru import logger
from tqsdk import TqApi

from shared.redis_client import RedisClient
from shared.config import Config
from closetoday_splitter import split_close_order
from executor import execute_order
from order_db_writer import OrderDbWriter


def process_order_submit(api: TqApi, redis_client: RedisClient, db_writer: OrderDbWriter,
                        config: Config, message: dict) -> bool:
    """
    Process order submit request with validations.

    Returns True for ACK, False for NACK without requeue
    """
    try:
        # Skip CANCEL requests (handled by canceller service)
        if message.get('action') == 'CANCEL':
            logger.debug("Skipping CANCEL request")
            return True

        logger.info(f"Processing order: {message}")

        # Split CLOSETODAY orders for SHFE/INE exchanges
        orders = split_close_order(message, redis_client, config.portfolio_id)

        # Execute all orders
        success = True
        for order in orders:
            if not execute_order(api, db_writer, config, order):
                success = False

        return success

    except Exception as e:
        logger.error(f"Error processing order: {e}")
        return False
