"""
Order monitoring logic using TqApi wait_update()
"""
from typing import Dict, Any, Callable
from loguru import logger
from tqsdk import TqApi
import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')
from shared.models import OrderHistoryFuturesChn


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

        # Process each order and check if it changed
        for order_id, order in orders.items():
            current_state = {
                'status': order.status,
                'volume_left': order.volume_left,
                'volume_orign': order.volume_orign,
                'exchange_order_id': getattr(order, 'exchange_order_id', ''),
                'exchange_id': getattr(order, 'exchange_id', '')
            }

            # Check against our tracking to detect changes
            prev = self.previous_orders.get(order_id)
            if prev is None or self._order_changed(prev, current_state):
                # Debug: Log raw TqSDK order attributes for FINISHED orders
                if order.status == "FINISHED":
                    logger.info(f"[DEBUG] Raw TqSDK order {order_id}: "
                               f"is_dead={getattr(order, 'is_dead', 'MISSING')} "
                               f"is_error={getattr(order, 'is_error', 'MISSING')} "
                               f"is_online={getattr(order, 'is_online', 'MISSING')} "
                               f"exchange_id={getattr(order, 'exchange_id', 'MISSING')} "
                               f"exchange_order_id={getattr(order, 'exchange_order_id', 'MISSING')}")

                # Convert TqSDK order to OrderHistoryFuturesChn model
                order_model = OrderHistoryFuturesChn.from_tqsdk_order(order, self.portfolio_id)

                # Determine event type
                event_type = self._determine_event_type(order)

                # Create update dict with all fields
                update = order_model.to_dict()
                update['type'] = 'ORDER_UPDATE'
                update['event_type'] = event_type

                # Debug log for troubleshooting
                logger.info(f"Order update: {order_id} {event_type} status={order.status} volume_left={order.volume_left} "
                           f"is_dead={order_model.is_dead} exchange_id={order_model.exchange_id} "
                           f"exchange_order_id={order_model.exchange_order_id}")
                on_update(update)

                # Update our tracking
                self.previous_orders[order_id] = current_state

    def _order_changed(self, prev: Dict[str, Any], curr: Dict[str, Any]) -> bool:
        """Check if order state changed - comparing key mutable fields"""
        if prev is None:
            return True

        # Check all fields that can change during order lifecycle
        return (prev.get('status') != curr.get('status') or
                prev.get('volume_left') != curr.get('volume_left') or
                prev.get('volume_orign') != curr.get('volume_orign') or
                prev.get('exchange_order_id') != curr.get('exchange_order_id') or
                prev.get('exchange_id') != curr.get('exchange_id'))

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
