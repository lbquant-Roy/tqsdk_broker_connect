"""
Order executor for handling order requests from RabbitMQ
"""
import json
import pika
import threading
import time
from typing import Optional, Dict, Any
from loguru import logger

from .config import Config
from .tq_data_stream import TqDataStreamHandler


class OrderExecutor:
    """Execute orders from RabbitMQ queue using TqApi"""

    # Exchanges that require CLOSETODAY for same-day positions
    CLOSETODAY_EXCHANGES = {"SHFE", "INE"}  # Shanghai Futures Exchange, International Energy Exchange

    def __init__(self, config: Config, stream_handler: TqDataStreamHandler):
        """
        Initialize order executor

        Parameters
        ----------
        config : Config
            Configuration instance
        stream_handler : TqDataStreamHandler
            TQ data stream handler instance
        """
        self.config = config
        self.stream_handler = stream_handler

        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        self.running = False
        self.executor_thread: Optional[threading.Thread] = None

    def start(self):
        """Start order executor"""
        if self.running:
            logger.warning("Order executor already running")
            return

        logger.info("Starting order executor")

        try:
            # Start executor thread
            self.running = True
            self.executor_thread = threading.Thread(target=self._executor_loop, daemon=True)
            self.executor_thread.start()

            logger.info("Order executor started successfully")

        except Exception as e:
            logger.error(f"Failed to start order executor: {e}")
            raise

    def _executor_loop(self):
        """Main executor loop - connects to RabbitMQ and consumes messages"""
        logger.info("Starting executor loop")

        while self.running:
            try:
                # Connect to RabbitMQ
                self._connect_rabbitmq()

                # Start consuming messages
                logger.info("Starting to consume order requests")
                self.channel.start_consuming()

            except pika.exceptions.AMQPConnectionError as e:
                logger.error(f"RabbitMQ connection error: {e}")
                time.sleep(5)  # Wait before reconnecting
            except Exception as e:
                logger.error(f"Error in executor loop: {e}")
                time.sleep(5)
            finally:
                self._disconnect_rabbitmq()

        logger.info("Executor loop stopped")

    def _connect_rabbitmq(self):
        """Connect to RabbitMQ and setup queue"""
        try:
            rabbitmq_config = self.config.rabbitmq

            # Create connection
            parameters = pika.URLParameters(rabbitmq_config['url'])
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Declare exchange
            exchange_name = rabbitmq_config['order_request_exchange']
            self.channel.exchange_declare(
                exchange=exchange_name,
                exchange_type='topic',
                durable=True
            )

            # Declare queue
            queue_name = rabbitmq_config['order_request_queue']
            self.channel.queue_declare(queue=queue_name, durable=True)

            # Bind queue to exchange with routing key
            routing_key = self.config.get_rabbitmq_routing_key()
            self.channel.queue_bind(
                exchange=exchange_name,
                queue=queue_name,
                routing_key=routing_key
            )

            # Also bind with wildcard for flexibility
            self.channel.queue_bind(
                exchange=exchange_name,
                queue=queue_name,
                routing_key='#'
            )

            # Setup consumer
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=self._on_order_message
            )

            logger.info(f"Connected to RabbitMQ, listening on queue: {queue_name}")

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def _disconnect_rabbitmq(self):
        """Disconnect from RabbitMQ"""
        try:
            if self.channel and self.channel.is_open:
                self.channel.stop_consuming()
                self.channel.close()

            if self.connection and self.connection.is_open:
                self.connection.close()

            logger.info("Disconnected from RabbitMQ")

        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {e}")

    def _on_order_message(self, ch, method, properties, body):
        """
        Callback for order messages from RabbitMQ

        Parameters
        ----------
        ch : channel
            RabbitMQ channel
        method : method
            Delivery method
        properties : properties
            Message properties
        body : bytes
            Message body
        """
        try:
            # Parse order request
            order_request = json.loads(body.decode('utf-8'))
            logger.info(f"Received order request: {order_request}")

            # Check if this is a cancel request
            action = order_request.get('action', 'SUBMIT')

            if action == 'CANCEL':
                cancel_type = order_request.get('type', 'order_id')
                if cancel_type == 'contract_code':
                    success = self.cancel_orders_by_contract(order_request.get('contract_code', ''))
                elif cancel_type == 'order_id':
                    success = self.cancel_order(order_request.get('order_id'))
                else:
                    logger.error(f"Unknown cancel type: {cancel_type}")
                    success = False
            else:
                # Handle normal order submission
                success = self._execute_order(order_request)

            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)

            if success:
                logger.info(f"Order request processed successfully: {order_request.get('order_id')}")
            else:
                logger.warning(f"Order request processing failed: {order_request.get('order_id')}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse order request: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"Error processing order message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def _execute_order(self, order_request: Dict[str, Any]) -> bool:
        """
        Execute order via TqApi with CLOSETODAY handling for SHFE/INE

        Parameters
        ----------
        order_request : dict
            Order request data containing:
            - symbol: str
            - direction: str (BUY/SELL)
            - offset: str (OPEN/CLOSE/CLOSETODAY)
            - volume: int
            - order_id: str
            - limit_price: float (optional)

        Returns
        -------
        bool
            True if order submitted successfully
        """
        try:
            api = self.stream_handler.get_api()
            if not api:
                logger.error("TqApi not available")
                return False

            # Extract order parameters
            symbol = order_request['symbol']
            direction = order_request['direction']
            offset = order_request.get('offset', 'OPEN')
            volume = int(order_request['volume'])
            order_id = order_request.get('order_id', '')
            limit_price = order_request.get('limit_price')

            logger.info(
                f"Executing order: {symbol} {direction} {offset} "
                f"{volume} @ {limit_price if limit_price else 'market'}"
            )

            # Handle CLOSETODAY splitting for SHFE/INE exchanges
            if offset == "CLOSE" and self._requires_closetoday(symbol):
                return self._execute_close_order_with_split(
                    api, symbol, direction, volume, limit_price, order_id
                )
            else:
                # Normal order execution
                return self._submit_single_order(
                    api, symbol, direction, offset, volume, limit_price, order_id
                )

        except Exception as e:
            logger.error(f"Failed to execute order: {e}")
            return False

    def _requires_closetoday(self, symbol: str) -> bool:
        """Check if symbol's exchange requires CLOSETODAY"""
        exchange = symbol.split('.')[0]
        return exchange in self.CLOSETODAY_EXCHANGES

    def _execute_close_order_with_split(
        self, api, symbol: str, direction: str, volume: int, limit_price: float, base_order_id: str
    ) -> bool:
        """
        Execute close order with CLOSETODAY/CLOSE splitting for SHFE/INE

        Parameters
        ----------
        api : TqApi
            TqApi instance
        symbol : str
            Trading symbol
        direction : str
            Order direction (BUY/SELL)
        volume : int
            Total volume to close
        limit_price : float
            Limit price
        base_order_id : str
            Base order ID for tracking

        Returns
        -------
        bool
            True if all orders submitted successfully
        """
        try:
            # Get position details from cache (thread-safe, no wait_update needed)
            pos_breakdown = self.stream_handler.get_position_breakdown(symbol)

            if not pos_breakdown:
                logger.warning(f"No position found for {symbol}, submitting as CLOSE")
                return self._submit_single_order(
                    api, symbol, direction, "CLOSE", volume, limit_price, base_order_id
                )

            # Determine which side to close
            if direction == "SELL":  # Closing long position
                today_qty = pos_breakdown['pos_long_today']
                his_qty = pos_breakdown['pos_long_his']
            else:  # direction == "BUY", closing short position
                today_qty = pos_breakdown['pos_short_today']
                his_qty = pos_breakdown['pos_short_his']

            logger.info(f"Position breakdown for {symbol}: today={today_qty}, historical={his_qty}")

            remaining_volume = volume
            submitted_count = 0

            # Close today's position first with CLOSETODAY
            if today_qty > 0 and remaining_volume > 0:
                closetoday_volume = min(today_qty, remaining_volume)
                closetoday_order_id = f"{base_order_id}_closetoday" if base_order_id else None

                success = self._submit_single_order(
                    api, symbol, direction, "CLOSETODAY", closetoday_volume,
                    limit_price, closetoday_order_id
                )

                if success:
                    remaining_volume -= closetoday_volume
                    submitted_count += 1
                    logger.info(f"Submitted CLOSETODAY order: {closetoday_volume} lots")
                else:
                    logger.error("Failed to submit CLOSETODAY order")
                    return False

            # Close historical position with CLOSE
            if his_qty > 0 and remaining_volume > 0:
                close_volume = min(his_qty, remaining_volume)
                close_order_id = f"{base_order_id}_close" if base_order_id else None

                success = self._submit_single_order(
                    api, symbol, direction, "CLOSE", close_volume,
                    limit_price, close_order_id
                )

                if success:
                    submitted_count += 1
                    logger.info(f"Submitted CLOSE order: {close_volume} lots")
                else:
                    logger.error("Failed to submit CLOSE order")
                    return False

            if submitted_count > 0:
                logger.info(f"Successfully submitted {submitted_count} close orders for {symbol}")
                return True
            else:
                logger.warning(f"No close orders submitted for {symbol}")
                return False

        except Exception as e:
            logger.error(f"Failed to execute close order with split: {e}")
            return False

    def _submit_single_order(
        self, api, symbol: str, direction: str, offset: str, volume: int,
        limit_price: float, order_id: str
    ) -> bool:
        """Submit a single order to TqApi"""
        try:
            if limit_price:
                order = api.insert_order(
                    symbol=symbol,
                    direction=direction,
                    offset=offset,
                    volume=volume,
                    limit_price=float(limit_price),
                    order_id=order_id if order_id else None
                )
            else:
                # Market order
                order = api.insert_order(
                    symbol=symbol,
                    direction=direction,
                    offset=offset,
                    volume=volume,
                    order_id=order_id if order_id else None
                )

            logger.info(f"Order submitted to TqApi: {order.order_id} ({offset} {volume} lots)")
            return True

        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            return False

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order by queuing the request to TqDataStreamHandler

        This method queues the cancel request instead of calling TqApi directly
        to ensure thread safety. The cancel request will be processed in the
        TqDataStreamHandler's monitoring loop where wait_update() is called.

        Parameters
        ----------
        order_id : str
            Order ID to cancel

        Returns
        -------
        bool
            True if cancel request was queued successfully
        """
        try:
            # Queue the cancel request for thread-safe processing
            success = self.stream_handler.queue_cancel_order(order_id)

            if success:
                logger.info(f"Cancel request queued for order: {order_id}")
            else:
                logger.error(f"Failed to queue cancel request for order: {order_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to queue cancel order {order_id}: {e}")
            return False

    def cancel_orders_by_contract(self, contract_code: str) -> bool:
        """
        Queue cancellation requests for all alive orders of a contract.

        Parameters
        ----------
        contract_code : str
            Contract code to cancel (EXCHANGE.symbol)

        Returns
        -------
        bool
            True if all cancel requests were queued successfully
        """
        if not contract_code:
            logger.error("Missing contract_code in cancel request")
            return False

        try:
            api = self.stream_handler.get_api()
            if not api:
                logger.error("TqApi not available")
                return False

            def normalize_instrument_id(code: str) -> str:
                if not code:
                    return ""
                return code.split(".", 1)[-1]

            orders = api.get_order()
            alive_orders = [
                order for order in orders.values()
                if order.status == "ALIVE"
                and normalize_instrument_id(getattr(order, "instrument_id", "")) == normalize_instrument_id(contract_code)
            ]

            if not alive_orders:
                logger.warning(f"No alive orders found for contract: {contract_code}")
                return True

            all_queued = True
            for order in alive_orders:
                if not self.stream_handler.queue_cancel_order(order.order_id):
                    all_queued = False

            if all_queued:
                logger.info(f"Queued {len(alive_orders)} cancel requests for contract: {contract_code}")
            else:
                logger.error(f"Failed to queue some cancel requests for contract: {contract_code}")
            return all_queued

        except Exception as e:
            logger.error(f"Failed to queue cancel orders for contract {contract_code}: {e}")
            return False

    def stop(self):
        """Stop order executor"""
        logger.info("Stopping order executor")
        self.running = False

        # Disconnect from RabbitMQ
        self._disconnect_rabbitmq()

        if self.executor_thread:
            self.executor_thread.join(timeout=5)

        logger.info("Order executor stopped")
