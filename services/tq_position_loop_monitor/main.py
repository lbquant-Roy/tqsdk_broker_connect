#!/usr/bin/env python
"""
TQ Position Loop Monitor Service

Loop-based position monitoring for reconciliation and universe tracking.
Runs every 5 seconds to ensure Redis position data consistency.
"""
import signal
import sys

sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from loguru import logger
from tqsdk import TqApi

from shared.config import get_config
from shared.tqapi_factory import create_tqapi, close_tqapi
from shared.redis_client import RedisClient
from shared.product_universe import ProductUniverseLoader

from monitor import PositionLoopMonitor


class PositionLoopMonitorService:
    """Position Loop Monitor Service - reconciliation with direct Redis writes"""

    def __init__(self):
        self.config = get_config()
        self.api: TqApi = None
        self.redis_client: RedisClient = None
        self.universe_loader: ProductUniverseLoader = None
        self.monitor: PositionLoopMonitor = None

    def setup_logging(self):
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>pos_loop_monitor</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True
        )
        logger.add(
            "logs/tq_position_loop_monitor.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | pos_loop_monitor - {message}",
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
        logger.info("Starting TQ Position Loop Monitor Service")
        logger.info("=" * 50)

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            logger.info("Initializing Redis client...")
            self.redis_client = RedisClient(self.config)

            logger.info("Initializing universe loader...")
            self.universe_loader = ProductUniverseLoader(self.config)

            logger.info("Initializing TqApi...")
            self.api = create_tqapi(self.config)

            logger.info("Initializing monitor...")
            self.monitor = PositionLoopMonitor(
                self.api,
                self.config.portfolio_id,
                self.redis_client,
                self.universe_loader
            )

            logger.info("Starting position loop monitoring...")
            self.monitor.start()

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            self.shutdown()

    def shutdown(self):
        logger.info("Shutting down...")
        if self.api:
            close_tqapi(self.api)
        if self.redis_client:
            self.redis_client.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    service = PositionLoopMonitorService()
    service.run()
