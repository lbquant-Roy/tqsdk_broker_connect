"""
TqApi order cancellation logic
"""
from loguru import logger
from tqsdk import TqApi


def cancel_order(api: TqApi, order_id: str) -> bool:
    """
    Cancel an order via TqApi

    Returns True if cancel request sent successfully, False otherwise
    """
    try:
        orders = api.get_order()

        if order_id not in orders:
            logger.warning(f"Order not found: {order_id}")
            return False

        order = orders[order_id]
        if order.status != "ALIVE":
            logger.warning(f"Order not alive, cannot cancel: {order_id} status={order.status}")
            return True  # Not an error, order already finished

        logger.info(f"Cancelling order: {order_id}")
        api.cancel_order(order)

        # Wait for cancel to be processed
        while order.status == "ALIVE":
            api.wait_update()

        logger.info(f"Order cancelled: {order_id} status={order.status}")
        return True

    except Exception as e:
        logger.error(f"Failed to cancel order {order_id}: {e}")
        return False
