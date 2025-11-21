"""
TQ data stream handler for monitoring account updates
"""
import queue
import threading
import time
from typing import Dict, Any, Optional, Set
from tqsdk import TqApi, TqAuth, TqKq
from loguru import logger

from .config import Config
from .data_processor import DataProcessor


class TqDataStreamHandler:
    """Handle TqApi connection and monitor account data updates"""

    def __init__(self, config: Config, data_processor: DataProcessor):
        """
        Initialize TQ data stream handler

        Parameters
        ----------
        config : Config
            Configuration instance
        data_processor : DataProcessor
            Data processor instance
        """
        self.config = config
        self.data_processor = data_processor

        self.api: Optional[TqApi] = None
        self.account = None
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None

        # Track previous state for detecting changes
        self.previous_positions: Dict[str, float] = {}
        self.previous_orders: Dict[str, Dict[str, Any]] = {}
        self.monitored_symbols: Set[str] = set()

        # Cancel request queue for thread-safe order cancellation
        self.cancel_queue: queue.Queue = queue.Queue()

    def start(self, symbols: list = None):
        """
        Start TQ data stream monitoring

        Parameters
        ----------
        symbols : list, optional
            List of symbols to monitor positions for
        """
        if self.running:
            logger.warning("TQ data stream already running")
            return

        logger.info("Starting TQ data stream handler")

        try:
            # Initialize TqApi
            tq_config = self.config.tq
            auth = TqAuth(tq_config['username'], tq_config['password'])

            # Select account type based on run mode
            if self.config.run_mode == 'real':
                self.account = TqKq()
                logger.info("Using REAL trading account (TqKq)")
            else:
                # For sandbox/test mode, can use sim account or TqKq based on config
                self.account = TqKq()
                logger.info("Using sandbox/test account (TqKq)")

            self.api = TqApi(account=self.account, auth=auth)

            # Store symbols to monitor
            if symbols:
                self.monitored_symbols = set(symbols)
                logger.info(f"Monitoring {len(symbols)} symbols")

            # Start monitoring thread
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()

            logger.info("TQ data stream started successfully")

        except Exception as e:
            logger.error(f"Failed to start TQ data stream: {e}")
            raise

    def _initialize_state(self):
        """Initialize previous state from current TqApi data"""
        try:
            # Wait for initial data
            self.api.wait_update()

            # Get initial positions
            positions = self.api.get_position()
            for symbol, pos in positions.items():
                net_pos = pos.pos_long - pos.pos_short
                if net_pos != 0:
                    self.previous_positions[symbol] = net_pos
                    # Also store in data processor
                    self.data_processor.process_position_update(symbol, net_pos)

            # Get initial orders
            orders = self.api.get_order()
            for order_id, order in orders.items():
                self.previous_orders[order_id] = {
                    'status': order.status,
                    'volume_left': order.volume_left,
                    'volume_orign': order.volume_orign
                }

            # Store initial account info
            account = self.api.get_account()
            account_data = {
                'balance': account.balance,
                'available': account.available,
                'margin': account.margin,
                'risk_ratio': account.risk_ratio
            }
            self.data_processor.store_account_info(account_data)

            logger.info(f"Initialized state: {len(self.previous_positions)} positions, {len(self.previous_orders)} orders")

        except Exception as e:
            logger.error(f"Failed to initialize state: {e}")

    def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Starting monitoring loop")

        # Initialize state before starting the loop
        self._initialize_state()

        while self.running:
            try:
                # Process pending cancel requests
                self._process_cancel_requests()

                # Wait for data updates from TqApi
                self.api.wait_update()

                # Check for position changes
                self._check_position_updates()

                # Check for order updates
                self._check_order_updates()

                # Update account info periodically
                self._update_account_info()

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1)

        logger.info("Monitoring loop stopped")

    def _process_cancel_requests(self):
        """Process pending cancel requests from the queue"""
        try:
            # Process all pending cancel requests (non-blocking)
            while not self.cancel_queue.empty():
                try:
                    order_id = self.cancel_queue.get_nowait()
                    logger.info(f"Processing cancel request for order: {order_id}")

                    # Get the order object to monitor status changes
                    orders = self.api.get_order()
                    order = orders.get(order_id)

                    if not order:
                        logger.warning(f"Order {order_id} not found, may already be cancelled or filled")
                        continue

                    # Only cancel if order is still alive
                    if order.status != "ALIVE":
                        logger.info(f"Order {order_id} is already {order.status}, no need to cancel")
                        continue

                    # Send cancel request
                    self.api.cancel_order(order_id)
                    logger.info(f"Cancel request sent for order: {order_id}")

                    # Wait for order status to change to FINISHED
                    # Use a timeout to prevent infinite loops
                    max_wait_iterations = 50  # ~5 seconds with typical wait_update timing
                    iterations = 0

                    while order.status == "ALIVE" and iterations < max_wait_iterations:
                        self.api.wait_update()
                        iterations += 1

                    if order.status == "FINISHED":
                        logger.info(f"Order {order_id} successfully cancelled: {order.last_msg}")
                    else:
                        logger.warning(f"Order {order_id} cancel timeout, final status: {order.status}")

                except queue.Empty:
                    break
                except Exception as e:
                    logger.error(f"Error processing cancel request: {e}")

        except Exception as e:
            logger.error(f"Error in cancel request processing: {e}")

    def _check_position_updates(self):
        """Check for position changes and update"""
        try:
            positions = self.api.get_position()
            current_positions = {}

            for symbol, pos in positions.items():
                net_pos = pos.pos_long - pos.pos_short
                current_positions[symbol] = net_pos

                # Check if position changed
                prev_pos = self.previous_positions.get(symbol, 0)
                if net_pos != prev_pos:
                    logger.info(f"Position changed: {symbol} {prev_pos} -> {net_pos}")
                    self.data_processor.process_position_update(symbol, net_pos)
                    self.previous_positions[symbol] = net_pos

            # Check for symbols that are no longer in positions
            for symbol in list(self.previous_positions.keys()):
                if symbol not in current_positions or current_positions[symbol] == 0:
                    if self.previous_positions[symbol] != 0:
                        logger.info(f"Position cleared: {symbol}")
                        self.data_processor.process_position_update(symbol, 0)
                        self.previous_positions[symbol] = 0

        except Exception as e:
            logger.error(f"Error checking position updates: {e}")

    def _check_order_updates(self):
        """Check for order status changes and update"""
        try:
            orders = self.api.get_order()

            for order_id, order in orders.items():
                # Check if this is a new order or status changed
                prev_order = self.previous_orders.get(order_id)

                status_changed = (
                    prev_order is None or
                    prev_order['status'] != order.status or
                    prev_order['volume_left'] != order.volume_left
                )

                if status_changed:
                    filled_qty = order.volume_orign - order.volume_left

                    # Determine event type
                    event_type = order.status
                    if order.status == 'FINISHED':
                        event_type = 'COMPLETE_FILL' if filled_qty == order.volume_orign else 'PARTIAL_FILL'

                    order_data = {
                        'order_id': order_id,
                        'status': order.status,
                        'filled_quantity': filled_qty,
                        'event_type': event_type,
                        'symbol': order.instrument_id,
                        'direction': order.direction,
                        'offset': order.offset,
                        'volume_orign': order.volume_orign,
                        'volume_left': order.volume_left,
                        'limit_price': order.limit_price
                    }

                    logger.info(f"Order updated: {order_id} - {order.status}, filled: {filled_qty}/{order.volume_orign}")
                    self.data_processor.process_order_update(order_data)

                    # Update tracking
                    self.previous_orders[order_id] = {
                        'status': order.status,
                        'volume_left': order.volume_left,
                        'volume_orign': order.volume_orign
                    }

        except Exception as e:
            logger.error(f"Error checking order updates: {e}")

    def _update_account_info(self):
        """Update account information"""
        try:
            account = self.api.get_account()
            account_data = {
                'balance': account.balance,
                'available': account.available,
                'margin': account.margin,
                'risk_ratio': account.risk_ratio,
                'position_profit': account.position_profit
            }
            self.data_processor.store_account_info(account_data)

        except Exception as e:
            logger.error(f"Error updating account info: {e}")

    def stop(self):
        """Stop TQ data stream monitoring"""
        logger.info("Stopping TQ data stream handler")
        self.running = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        if self.api:
            try:
                self.api.close()
                logger.info("TqApi connection closed")
            except Exception as e:
                logger.error(f"Error closing TqApi: {e}")

        logger.info("TQ data stream stopped")

    def get_api(self) -> Optional[TqApi]:
        """
        Get TqApi instance for direct access

        Returns
        -------
        TqApi or None
            TqApi instance if running
        """
        return self.api

    def queue_cancel_order(self, order_id: str) -> bool:
        """
        Queue an order cancellation request for thread-safe processing

        Parameters
        ----------
        order_id : str
            Order ID to cancel

        Returns
        -------
        bool
            True if request was queued successfully
        """
        try:
            self.cancel_queue.put(order_id, block=False)
            logger.info(f"Queued cancel request for order: {order_id}")
            return True
        except queue.Full:
            logger.error(f"Cancel queue is full, cannot queue order: {order_id}")
            return False
