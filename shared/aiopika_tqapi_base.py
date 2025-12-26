#!/usr/bin/env python
"""
Base class for aio-pika + TqSDK dual-thread services
"""
import asyncio
import threading
import queue
import signal
import sys
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import pandas as pd

from loguru import logger
from tqsdk import TqApi
import aio_pika

from shared.config import get_config
from shared.tqapi_factory import create_tqapi, close_tqapi


class AioPikaTqApiService(ABC):

    def __init__(self):
        self.config = get_config()

        # Worker thread components
        self.api: Optional[TqApi] = None
        self.message_queue = queue.Queue(maxsize=100)
        self.worker_thread: Optional[threading.Thread] = None
        self.worker_running = threading.Event()

        # Async components
        self.heartbeat_alive = False
        self.shutdown_event = asyncio.Event()

        # Health check settings
        self.block_timeout = 10
        self.block_counter_max = 3

    @abstractmethod
    def get_queue_name(self) -> str:
        pass

    @abstractmethod
    def get_exchange_name(self) -> str:
        pass

    @abstractmethod
    def get_service_name(self) -> str:
        pass

    @abstractmethod
    def initialize_worker_resources(self):
        pass

    @abstractmethod
    def cleanup_worker_resources(self):
        pass

    @abstractmethod
    def process_message_in_worker(self, message: dict) -> bool:
        """Return True for ACK, False for NACK"""
        pass

    def _in_trading_time(self) -> bool:
        now_ts = pd.Timestamp.now(tz="Asia/Shanghai")
        time_in_minutes = now_ts.hour * 60 + now_ts.minute

        morning_1 = (9 * 60, 10 * 60 + 15)
        morning_2 = (10 * 60 + 30, 11 * 60 + 30)
        afternoon = (13 * 60 + 30, 15 * 60)

        return (morning_1[0] <= time_in_minutes <= morning_1[1] or
                morning_2[0] <= time_in_minutes <= morning_2[1] or
                afternoon[0] <= time_in_minutes <= afternoon[1])

    def tqapi_worker_loop(self):
        logger.info("Worker thread starting...")

        try:
            logger.info("Initializing TqApi in worker thread...")
            self.api = create_tqapi(self.config)
            self.initialize_worker_resources()

            logger.info("Worker thread ready")
            block_counter = 0

            while self.worker_running.is_set():
                block_res = self.api.wait_update(deadline=time.time() + self.block_timeout)

                if not block_res:
                    if self._in_trading_time():
                        block_counter += 1
                        logger.warning(f"TqSDK timeout ({block_counter}/{self.block_counter_max})")
                    else:
                        logger.debug("TqSDK timeout outside trading hours")
                else:
                    block_counter = 0

                if block_counter > self.block_counter_max:
                    raise Exception(f"Too many TqSDK timeouts, shutting down")

                try:
                    message = self.message_queue.get_nowait()
                    logger.info("Processing message from queue")

                    try:
                        success = self.process_message_in_worker(message)
                        if not success:
                            logger.warning("Message processing failed")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)

                except queue.Empty:
                    pass

        except Exception as e:
            logger.error(f"Fatal worker error: {e}", exc_info=True)
        finally:
            logger.info("Worker thread shutting down...")
            try:
                self.cleanup_worker_resources()
            except Exception as e:
                logger.error(f"Error cleaning up: {e}")

            if self.api:
                close_tqapi(self.api)

    async def consume_messages_async(self):
        logger.info("Starting aio-pika consumer...")

        queue_name = self.get_queue_name()
        exchange_name = self.get_exchange_name()
        routing_key = f"PortfolioId_{self.config.portfolio_id}"

        while not self.shutdown_event.is_set():
            try:
                connection = await aio_pika.connect_robust(self.config.rabbitmq['url'])
                self.heartbeat_alive = True
                logger.info("Connected to RabbitMQ")

                async with connection:
                    channel = await connection.channel()
                    await channel.set_qos(prefetch_count=1)

                    exchange = await channel.declare_exchange(
                        exchange_name,
                        aio_pika.ExchangeType.TOPIC,
                        durable=True
                    )

                    queue_obj = await channel.declare_queue(queue_name, durable=True)
                    await queue_obj.bind(exchange, routing_key)

                    logger.info(f"Bound to {queue_name} with key {routing_key}")

                    async with queue_obj.iterator() as queue_iter:
                        async for message in queue_iter:
                            async with message.process():
                                try:
                                    message_dict = json.loads(message.body)

                                    try:
                                        self.message_queue.put_nowait(message_dict)
                                    except queue.Full:
                                        logger.warning("Queue full, dropping message")
                                        raise Exception("Queue full")

                                except json.JSONDecodeError as e:
                                    logger.error(f"Invalid JSON: {e}")

                            if self.shutdown_event.is_set():
                                break

            except asyncio.CancelledError:
                logger.info("Consumer cancelled")
                break
            except Exception as e:
                self.heartbeat_alive = False
                logger.error(f"Consumer error: {e}", exc_info=True)
                if not self.shutdown_event.is_set():
                    await asyncio.sleep(5)

        logger.info("Consumer stopped")

    async def heartbeat_task(self):
        logger.info("Starting heartbeat...")

        while not self.shutdown_event.is_set():
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if self.heartbeat_alive:
                logger.info(f"[HEARTBEAT] {timestamp} - OK")
            else:
                logger.warning(f"[HEARTBEAT] {timestamp} - RabbitMQ disconnected")

            if self.worker_thread and not self.worker_thread.is_alive():
                logger.error("Worker thread died!")
                self.shutdown_event.set()
                break

            await asyncio.sleep(1)

        logger.info("Heartbeat stopped")

    async def start_async_tasks(self):
        consumer_task = asyncio.create_task(self.consume_messages_async())
        heartbeat = asyncio.create_task(self.heartbeat_task())

        await self.shutdown_event.wait()

        consumer_task.cancel()
        heartbeat.cancel()

        await asyncio.gather(consumer_task, heartbeat, return_exceptions=True)

    def setup_logging(self):
        service_name = self.get_service_name()

        logger.remove()
        logger.add(
            sys.stdout,
            format=f"<green>{{time:YYYY-MM-DD HH:mm:ss}}</green> | <level>{{level: <8}}</level> | <cyan>{service_name}</cyan> - <level>{{message}}</level>",
            level="INFO",
            colorize=True
        )
        logger.add(
            f"logs/{service_name}.log",
            format=f"{{time:YYYY-MM-DD HH:mm:ss}} | {{level: <8}} | {service_name} - {{message}}",
            level="INFO",
            rotation="10 MB",
            retention="7 days"
        )

    def signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}")
        self.shutdown()

    def shutdown(self):
        logger.info("Shutting down...")

        self.shutdown_event.set()
        self.worker_running.clear()

        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)

        logger.info("Shutdown complete")

    def run(self):
        self.setup_logging()

        logger.info("=" * 60)
        logger.info(f"Starting {self.get_service_name()}")
        logger.info("=" * 60)

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            self.worker_running.set()
            self.worker_thread = threading.Thread(
                target=self.tqapi_worker_loop,
                daemon=False
            )
            self.worker_thread.start()
            logger.info("Worker thread started")

            asyncio.run(self.start_async_tasks())

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            self.shutdown()
