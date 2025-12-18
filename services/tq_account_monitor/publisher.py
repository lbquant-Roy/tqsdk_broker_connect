"""
RabbitMQ publisher for account updates
"""
from typing import Dict, Any
from loguru import logger

import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from shared.config import Config
from shared.constants import INTERNAL_EXCHANGE, ROUTING_KEY_ACCOUNT_UPDATES
from shared.rabbitmq_client import RabbitMQPublisher


class AccountUpdatePublisher:
    """Publisher for account updates to internal queue"""

    def __init__(self, config: Config):
        self.publisher = RabbitMQPublisher(
            config=config,
            exchange=INTERNAL_EXCHANGE,
            exchange_type="direct"
        )
        self.publisher.connect()

    def publish(self, update: Dict[str, Any]):
        """Publish account update to internal queue"""
        try:
            self.publisher.publish(ROUTING_KEY_ACCOUNT_UPDATES, update)
            logger.debug(f"Published account update")
        except Exception as e:
            logger.error(f"Failed to publish account update: {e}")

    def close(self):
        """Close publisher connection"""
        self.publisher.close()
