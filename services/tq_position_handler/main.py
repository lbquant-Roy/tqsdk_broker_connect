#!/usr/bin/env python
"""
TQ Position Handler Service

Consumes position updates from internal RabbitMQ and writes to Redis.
NO TqApi - pure data handler.
"""
import signal
import sys

sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from loguru import logger

from shared.config import get_config
from shared.constants import INTERNAL_EXCHANGE, INTERNAL_POSITION_UPDATES_QUEUE, ROUTING_KEY_POSITION_UPDATES
from shared.rabbitmq_client import RabbitMQConsumer
from shared.redis_client import RedisClient

from redis_writer import PositionRedisWriter


class PositionHandlerService:
    """Position Handler Service - NO TqApi, pure data handler"""

    def __init__(self):
        self.config = get_config()
        self.consumer: RabbitMQConsumer = None
        self.redis_client: RedisClient = None
        self.writer: PositionRedisWriter = None
        self.running = False

    def setup_logging(self):
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>position_handler</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True
        )
        logger.add(
            "logs/tq_position_handler.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | position_handler - {message}",
            level="INFO",
            rotation="10 MB",
            retention="7 days"
        )

    def signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        if self.consumer:
            self.consumer.stop()

    def process_update(self, message: dict) -> bool:
        """Process a position update"""
        try:
            logger.info(f"Processing position update: {message.get('symbol')}")
            return self.writer.write_position_update(message)
        except Exception as e:
            logger.error(f"Error processing position update: {e}")
            return False

    def run(self):
        self.setup_logging()
        logger.info("=" * 50)
        logger.info("Starting TQ Position Handler Service")
        logger.info("=" * 50)

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            logger.info("Initializing Redis client...")
            self.redis_client = RedisClient(self.config)
            self.writer = PositionRedisWriter(self.redis_client)

            logger.info("Initializing RabbitMQ consumer...")
            self.consumer = RabbitMQConsumer(
                config=self.config,
                queue=INTERNAL_POSITION_UPDATES_QUEUE,
                exchange=INTERNAL_EXCHANGE,
                routing_key=ROUTING_KEY_POSITION_UPDATES,
                exchange_type="direct"
            )

            self.running = True
            logger.info("Starting to consume position updates...")
            self.consumer.consume(self.process_update)

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
        if self.redis_client:
            self.redis_client.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    service = PositionHandlerService()
    service.run()
