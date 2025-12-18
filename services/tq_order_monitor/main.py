#!/usr/bin/env python
"""
TQ Order Monitor Service

Monitors order changes via TqApi and publishes updates to internal RabbitMQ.
"""
import signal
import sys

sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from loguru import logger
from tqsdk import TqApi

from shared.config import get_config
from shared.tqapi_factory import create_tqapi, close_tqapi

from monitor import OrderMonitor
from publisher import OrderUpdatePublisher


class OrderMonitorService:
    """Order Monitor Service - owns its own TqApi instance"""

    def __init__(self):
        self.config = get_config()
        self.api: TqApi = None
        self.monitor: OrderMonitor = None
        self.publisher: OrderUpdatePublisher = None

    def setup_logging(self):
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>order_monitor</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True
        )
        logger.add(
            "logs/tq_order_monitor.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | order_monitor - {message}",
            level="INFO",
            rotation="10 MB",
            retention="7 days"
        )

    def signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        if self.monitor:
            self.monitor.stop()

    def run(self):
        self.setup_logging()
        logger.info("=" * 50)
        logger.info("Starting TQ Order Monitor Service")
        logger.info("=" * 50)

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            logger.info("Initializing TqApi...")
            self.api = create_tqapi(self.config)

            logger.info("Initializing publisher...")
            self.publisher = OrderUpdatePublisher(self.config)

            logger.info("Initializing monitor...")
            self.monitor = OrderMonitor(self.api, self.config.portfolio_id)

            logger.info("Starting order monitoring...")
            self.monitor.start(self.publisher.publish)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            self.shutdown()

    def shutdown(self):
        logger.info("Shutting down...")
        if self.publisher:
            self.publisher.close()
        if self.api:
            close_tqapi(self.api)
        logger.info("Shutdown complete")


if __name__ == "__main__":
    service = OrderMonitorService()
    service.run()
