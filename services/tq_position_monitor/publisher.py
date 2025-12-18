"""
RabbitMQ publisher for position updates
"""
from typing import Dict, Any
from loguru import logger

import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from shared.config import Config
from shared.constants import INTERNAL_EXCHANGE, ROUTING_KEY_POSITION_UPDATES
from shared.rabbitmq_client import RabbitMQPublisher


class PositionUpdatePublisher:
    """Publisher for position updates to internal queue"""

    def __init__(self, config: Config):
        self.publisher = RabbitMQPublisher(
            config=config,
            exchange=INTERNAL_EXCHANGE,
            exchange_type="direct"
        )
        self.publisher.connect()

    def publish(self, update: Dict[str, Any]):
        """Publish position update to internal queue"""
        try:
            self.publisher.publish(ROUTING_KEY_POSITION_UPDATES, update)
            logger.debug(f"Published position update: {update.get('symbol')}")
        except Exception as e:
            logger.error(f"Failed to publish position update: {e}")

    def close(self):
        """Close publisher connection"""
        self.publisher.close()
