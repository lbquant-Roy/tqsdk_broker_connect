"""
RabbitMQ consumer for order submit requests
"""
from typing import Dict, Any
from loguru import logger

import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from shared.config import Config
from shared.constants import EXTERNAL_ORDER_SUBMIT_QUEUE, EXTERNAL_ORDER_EXCHANGE
from shared.rabbitmq_client import RabbitMQConsumer


def create_consumer(config: Config) -> RabbitMQConsumer:
    """Create RabbitMQ consumer for order submit requests"""
    routing_key = f"PortfolioId_{config.portfolio_id}"

    return RabbitMQConsumer(
        config=config,
        queue=EXTERNAL_ORDER_SUBMIT_QUEUE,
        exchange=EXTERNAL_ORDER_EXCHANGE,
        routing_key=routing_key,
        exchange_type="topic"
    )
