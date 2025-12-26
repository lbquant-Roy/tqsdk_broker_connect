"""
Order cancellation worker logic
Runs in worker thread, processes cancel requests
"""
import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from loguru import logger
from tqsdk import TqApi

from executor import cancel_order, cancel_orders_by_contract, cancel_all


def process_order_cancel(api: TqApi, message: dict) -> bool:
    """
    Process order cancel request.

    Returns True for ACK, False for NACK without requeue
    """
    try:
        # Only process CANCEL requests
        if message.get('action') != 'CANCEL':
            logger.debug("Skipping non-CANCEL request")
            return True

        cancel_type = message.get('type', 'order_id')

        if cancel_type == 'contract_code':
            contract_code = message.get('contract_code')
            if not contract_code:
                logger.error("Missing contract_code")
                return False
            logger.info(f"Cancelling orders for contract: {contract_code}")
            return cancel_orders_by_contract(api, contract_code)
        elif cancel_type == 'order_id':
            order_id = message.get('order_id')
            if not order_id:
                logger.error("Missing order_id")
                return False

            logger.info(f"Cancelling order: {order_id}")
            return cancel_order(api, order_id)
        elif cancel_type == "all":
            logger.info("Cancelling all alive orders")
            return cancel_all(api, None)
        else:
            logger.error(f"Unknown cancel type: {cancel_type}")
            return False

    except Exception as e:
        logger.error(f"Error processing cancel: {e}")
        return False
