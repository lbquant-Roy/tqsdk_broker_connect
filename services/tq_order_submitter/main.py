#!/usr/bin/env python
"""
TQ Order Submitter Service

Consumes SUBMIT order requests from external RabbitMQ and executes via TqApi.
Handles CLOSETODAY splitting for SHFE/INE exchanges.
"""
import signal
import sys

sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from loguru import logger
from tqsdk import TqApi

from shared.config import get_config
from shared.tqapi_factory import create_tqapi, close_tqapi
from shared.redis_client import RedisClient
from shared.rabbitmq_client import RabbitMQConsumer
from shared.constants import EXTERNAL_ORDER_SUBMIT_QUEUE, EXTERNAL_ORDER_EXCHANGE

from closetoday_splitter import split_close_order
from executor import execute_order


class OrderSubmitterService:
    """Order Submitter Service - owns its own TqApi instance"""

    def __init__(self):
        self.config = get_config()
        self.api: TqApi = None
        self.redis_client: RedisClient = None
        self.consumer: RabbitMQConsumer = None
        self.running = False

    def setup_logging(self):
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>order_submitter</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True
        )
        logger.add(
            "logs/tq_order_submitter.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | order_submitter - {message}",
            level="INFO",
            rotation="10 MB",
            retention="7 days"
        )

    def signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        if self.consumer:
            self.consumer.stop()

    def process_order(self, message: dict) -> bool:
        """Process an order submit request"""
        try:
            # Skip cancel requests (handled by canceller service)
            if message.get('action') == 'CANCEL':
                logger.debug("Skipping CANCEL request (handled by canceller)")
                return True

            logger.info(f"Processing order: {message}")

            # Split order if needed (for SHFE/INE CLOSE orders)
            orders = split_close_order(
                message,
                self.redis_client,
                self.config.portfolio_id
            )

            # Execute all orders
            success = True
            for order in orders:
                if not execute_order(self.api, order):
                    success = False

            return success

        except Exception as e:
            logger.error(f"Error processing order: {e}")
            return False

    def run(self):
        self.setup_logging()
        logger.info("=" * 50)
        logger.info("Starting TQ Order Submitter Service")
        logger.info("=" * 50)

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            # Initialize components
            logger.info("Initializing Redis client...")
            self.redis_client = RedisClient(self.config)

            logger.info("Initializing TqApi...")
            self.api = create_tqapi(self.config)

            logger.info("Initializing RabbitMQ consumer...")
            routing_key = f"PortfolioId_{self.config.portfolio_id}"
            self.consumer = RabbitMQConsumer(
                config=self.config,
                queue=EXTERNAL_ORDER_SUBMIT_QUEUE,
                exchange=EXTERNAL_ORDER_EXCHANGE,
                routing_key=routing_key,
                exchange_type="topic"
            )

            self.running = True
            logger.info("Starting to consume order requests...")
            self.consumer.consume(self.process_order)

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
        if self.redis_client:
            self.redis_client.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    service = OrderSubmitterService()
    service.run()
