#!/usr/bin/env python
"""
TQ Order Canceller Service

Consumes CANCEL order requests from external RabbitMQ and cancels via TqApi.
"""
import signal
import sys

sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from loguru import logger
from tqsdk import TqApi

from shared.config import get_config
from shared.tqapi_factory import create_tqapi, close_tqapi
from shared.rabbitmq_client import RabbitMQConsumer
from shared.constants import EXTERNAL_ORDER_CANCEL_QUEUE, EXTERNAL_ORDER_EXCHANGE

from executor import cancel_order


class OrderCancellerService:
    """Order Canceller Service - owns its own TqApi instance"""

    def __init__(self):
        self.config = get_config()
        self.api: TqApi = None
        self.consumer: RabbitMQConsumer = None
        self.running = False

    def setup_logging(self):
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>order_canceller</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True
        )
        logger.add(
            "logs/tq_order_canceller.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | order_canceller - {message}",
            level="INFO",
            rotation="10 MB",
            retention="7 days"
        )

    def signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        if self.consumer:
            self.consumer.stop()

    def process_cancel(self, message: dict) -> bool:
        """Process an order cancel request"""
        try:
            # Only process cancel requests
            if message.get('action') != 'CANCEL':
                logger.debug("Skipping non-CANCEL request")
                return True

            order_id = message.get('order_id')
            if not order_id:
                logger.error("Missing order_id in cancel request")
                return False

            logger.info(f"Processing cancel: {order_id}")
            return cancel_order(self.api, order_id)

        except Exception as e:
            logger.error(f"Error processing cancel: {e}")
            return False

    def run(self):
        self.setup_logging()
        logger.info("=" * 50)
        logger.info("Starting TQ Order Canceller Service")
        logger.info("=" * 50)

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            logger.info("Initializing TqApi...")
            self.api = create_tqapi(self.config)

            logger.info("Initializing RabbitMQ consumer...")
            routing_key = f"PortfolioId_{self.config.portfolio_id}"
            self.consumer = RabbitMQConsumer(
                config=self.config,
                queue=EXTERNAL_ORDER_CANCEL_QUEUE,
                exchange=EXTERNAL_ORDER_EXCHANGE,
                routing_key=routing_key,
                exchange_type="topic"
            )

            self.running = True
            logger.info("Starting to consume cancel requests...")
            self.consumer.consume(self.process_cancel)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            self.shutdown()

    def shutdown(self):
        logger.info("Shutting down...")
        if self.consumer:
            self.consumer.close()
        if self.api:
            close_tqapi(self.api)
        logger.info("Shutdown complete")


if __name__ == "__main__":
    service = OrderCancellerService()
    service.run()
