"""
TqApi order cancellation logic
"""
import time
from loguru import logger
from tqsdk import TqApi

def cancel_all(api: TqApi, order_id: str) -> bool:
    """
    Cancel all alive orders via TqApi

    Args:
        api: TqApi instance
        order_id: Not used in this implementation (cancels all orders)

    Returns:
        True if all cancellations completed successfully, False otherwise
    """
    try:
        orders = api.get_order()

        alive_orders = [
            order for order in orders.values()
            if order.status == "ALIVE"
        ]

        if not alive_orders:
            logger.info("No alive orders to cancel")
            return True

        logger.info(f"Found {len(alive_orders)} alive orders to cancel")

        for order in alive_orders:
            try:
                logger.info(f"Cancelling order: {order.order_id}")
                api.cancel_order(order)

                start_time = time.time()
                timeout = 1.0

                while order.status == "ALIVE" and not order.is_dead:
                    if time.time() - start_time > timeout:
                        logger.error(f"Order cancel timeout after {timeout}s: {order.order_id}")
                        break

                    api.wait_update()

                if order.status == "FINISHED" or order.is_dead:
                    logger.info(f"Order cancelled successfully: {order.order_id}")
                else:
                    logger.warning(f"Order cancel failed: {order.order_id} status={order.status}")

            except Exception as e:
                logger.error(f"Failed to cancel order {order.order_id}: {e}")
                continue

        logger.info("Finished cancelling all alive orders")
        return True

    except Exception as e:
        logger.error(f"Failed to cancel all orders: {e}")
        return False


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


def cancel_orders_by_contract(api: TqApi, contract_code: str) -> bool:
    """
    Cancel all alive orders for a contract via TqApi.

    Returns True if the cancel flow completed, False otherwise.
    """
    try:
        orders = api.get_order()
        def normalize_instrument_id(code: str) -> str:
            if not code:
                return ""
            return code.split(".", 1)[-1]

        alive_orders = [
            order for order in orders.values()
            if order.status == "ALIVE"
            and normalize_instrument_id(getattr(order, "instrument_id", "")) == normalize_instrument_id(contract_code)
        ]

        if not alive_orders:
            logger.warning(f"No alive orders found for contract: {contract_code}")
            return True

        for order in alive_orders:
            logger.info(f"Cancelling order: {order.order_id} contract={contract_code}")
            api.cancel_order(order)

        while any(order.status == "ALIVE" for order in alive_orders):
            api.wait_update()

        logger.info(f"Cancelled {len(alive_orders)} orders for contract: {contract_code}")
        return True

    except Exception as e:
        logger.error(f"Failed to cancel orders for contract {contract_code}: {e}")
        return False
