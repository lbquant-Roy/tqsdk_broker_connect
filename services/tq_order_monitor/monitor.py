"""
Order monitoring logic using TqApi wait_update()
"""
from typing import Dict, Any, Callable
from loguru import logger
from tqsdk import TqApi


class OrderMonitor:
    """Monitor order changes from TqApi"""

    def __init__(self, api: TqApi, portfolio_id: str):
        self.api = api
        self.portfolio_id = portfolio_id
        self.previous_orders: Dict[str, Dict[str, Any]] = {}
        self.running = False

    def start(self, on_update: Callable[[Dict[str, Any]], None]):
        """Start monitoring order changes"""
        self.running = True
        logger.info("Order monitor started")

        while self.running:
            try:
                self.api.wait_update()
                self._check_order_updates(on_update)
            except Exception as e:
                if self.running:
                    logger.error(f"Error in order monitor loop: {e}")

    def stop(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Order monitor stopping...")

    def _check_order_updates(self, on_update: Callable[[Dict[str, Any]], None]):
        """Check for order changes and publish updates"""
        orders = self.api.get_order()
        current_orders: Dict[str, Dict[str, Any]] = {}

        for order_id, order in orders.items():
            current_orders[order_id] = {
                'status': order.status,
                'volume_left': order.volume_left,
                'volume_orign': order.volume_orign
            }

            # Check if order changed
            prev = self.previous_orders.get(order_id)
            if prev is None or self._order_changed(prev, current_orders[order_id]):
                # Determine event type
                event_type = self._determine_event_type(order)

                update = {
                    'type': 'ORDER_UPDATE',
                    'portfolio_id': self.portfolio_id,
                    'order_id': order_id,
                    'status': order.status,
                    'event_type': event_type,
                    'filled_quantity': order.volume_orign - order.volume_left,
                    'symbol': order.instrument_id,
                    'direction': order.direction,
                    'offset': order.offset,
                    'volume_orign': order.volume_orign,
                    'volume_left': order.volume_left,
                    'limit_price': order.limit_price
                }

                logger.info(f"Order update: {order_id} {event_type} status={order.status}")
                on_update(update)

        self.previous_orders = current_orders

    def _order_changed(self, prev: Dict[str, Any], curr: Dict[str, Any]) -> bool:
        """Check if order state changed"""
        return (prev['status'] != curr['status'] or
                prev['volume_left'] != curr['volume_left'])

    def _determine_event_type(self, order) -> str:
        """Determine event type based on order state"""
        if order.status == "FINISHED":
            if order.volume_left == 0:
                return "COMPLETE_FILL"
            else:
                return "CANCELED"
        elif order.status == "ALIVE":
            if order.volume_left < order.volume_orign:
                return "PARTIAL_FILL"
            else:
                return "NEW"
        return order.status
