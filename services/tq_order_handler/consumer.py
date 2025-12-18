"""
RabbitMQ consumer for order updates
"""
import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from shared.config import Config
from shared.constants import INTERNAL_EXCHANGE, INTERNAL_ORDER_UPDATES_QUEUE, ROUTING_KEY_ORDER_UPDATES
from shared.rabbitmq_client import RabbitMQConsumer


def create_consumer(config: Config) -> RabbitMQConsumer:
    """Create RabbitMQ consumer for order updates"""
    return RabbitMQConsumer(
        config=config,
        queue=INTERNAL_ORDER_UPDATES_QUEUE,
        exchange=INTERNAL_EXCHANGE,
        routing_key=ROUTING_KEY_ORDER_UPDATES,
        exchange_type="direct"
    )
