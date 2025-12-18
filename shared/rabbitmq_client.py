"""
RabbitMQ client helper for TqSDK Broker Connect services
"""
import json
import time
from typing import Callable, Optional, Any, Dict
import pika
from pika.exceptions import AMQPConnectionError
from loguru import logger

from .config import Config


class RabbitMQPublisher:
    """RabbitMQ publisher for sending messages to queues"""

    def __init__(self, config: Config, exchange: str = "", exchange_type: str = "direct"):
        self.config = config
        self.exchange = exchange
        self.exchange_type = exchange_type
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None

    def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            self.connection = pika.BlockingConnection(
                pika.URLParameters(self.config.rabbitmq['url'])
            )
            self.channel = self.connection.channel()

            if self.exchange:
                self.channel.exchange_declare(
                    exchange=self.exchange,
                    exchange_type=self.exchange_type,
                    durable=True
                )

            logger.info(f"RabbitMQ publisher connected (exchange: {self.exchange or 'default'})")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def publish(self, routing_key: str, message: Dict[str, Any], exchange: str = None):
        """Publish a message to the specified routing key"""
        if not self.channel:
            self.connect()

        try:
            self.channel.basic_publish(
                exchange=exchange or self.exchange,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent
                    content_type='application/json'
                )
            )
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            self.reconnect()
            raise

    def reconnect(self):
        """Reconnect to RabbitMQ"""
        self.close()
        time.sleep(5)
        self.connect()

    def close(self):
        """Close connection"""
        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
            except Exception as e:
                logger.error(f"Error closing RabbitMQ connection: {e}")


class RabbitMQConsumer:
    """RabbitMQ consumer for receiving messages from queues"""

    def __init__(self, config: Config, queue: str, exchange: str = "",
                 routing_key: str = "", exchange_type: str = "direct"):
        self.config = config
        self.queue = queue
        self.exchange = exchange
        self.routing_key = routing_key
        self.exchange_type = exchange_type
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        self.running = False

    def connect(self):
        """Establish connection and declare queue"""
        try:
            self.connection = pika.BlockingConnection(
                pika.URLParameters(self.config.rabbitmq['url'])
            )
            self.channel = self.connection.channel()

            # Declare exchange if specified
            if self.exchange:
                self.channel.exchange_declare(
                    exchange=self.exchange,
                    exchange_type=self.exchange_type,
                    durable=True
                )

            # Declare queue
            self.channel.queue_declare(queue=self.queue, durable=True)

            # Bind queue to exchange if specified
            if self.exchange and self.routing_key:
                self.channel.queue_bind(
                    exchange=self.exchange,
                    queue=self.queue,
                    routing_key=self.routing_key
                )

            # Set QoS
            self.channel.basic_qos(prefetch_count=1)

            logger.info(f"RabbitMQ consumer connected (queue: {self.queue})")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def consume(self, callback: Callable[[Dict[str, Any]], bool]):
        """
        Start consuming messages

        callback should return True if message processed successfully, False otherwise
        """
        if not self.channel:
            self.connect()

        self.running = True

        def on_message(ch, method, properties, body):
            if not self.running:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                return

            try:
                message = json.loads(body)
                success = callback(message)

                if success:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                else:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON message: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        self.channel.basic_consume(queue=self.queue, on_message_callback=on_message)

        logger.info(f"Starting to consume from {self.queue}")
        while self.running:
            try:
                self.connection.process_data_events(time_limit=1)
            except AMQPConnectionError:
                logger.warning("RabbitMQ connection lost, reconnecting...")
                self.reconnect()
            except Exception as e:
                if self.running:
                    logger.error(f"Error in consume loop: {e}")
                    time.sleep(5)

    def stop(self):
        """Stop consuming"""
        self.running = False
        logger.info("Consumer stopping...")

    def reconnect(self):
        """Reconnect to RabbitMQ"""
        self.close()
        time.sleep(5)
        self.connect()

    def close(self):
        """Close connection"""
        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
            except Exception as e:
                logger.error(f"Error closing RabbitMQ connection: {e}")
