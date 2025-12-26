#!/usr/bin/env python
"""
Demo: aio-pika async consumer + TqApi blocking loop integration

Architecture:
- Main thread: asyncio event loop with aio-pika + heartbeat
- Worker thread: TqApi wait_update() blocking loop
- Bridge: threading.Queue for order messages

Usage:
    # Terminal 1
    uv run python tests/demo_aiopika_tqapi_integration.py

    # Terminal 2
    uv run python tests/mq_mock_messages.py --type submit
"""
import asyncio
import threading
import queue
import signal
import sys
import json
from datetime import datetime
from typing import Optional
import time
import pandas as pd

sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from loguru import logger
from tqsdk import TqApi
import aio_pika

from shared.config import get_config
from shared.tqapi_factory import create_tqapi, close_tqapi
from shared.redis_client import RedisClient
from shared.constants import EXTERNAL_ORDER_SUBMIT_QUEUE, EXTERNAL_ORDER_EXCHANGE

from services.tq_order_submitter.closetoday_splitter import split_close_order
from services.tq_order_submitter.executor import execute_order


class AioPikaTqApiDemo:
    """
    Integration demo combining:
    - aio-pika async RabbitMQ consumer
    - TqApi blocking wait_update() loop
    - Threading queue bridge
    - Heartbeat monitoring
    """

    def __init__(self):
        self.config = get_config()

        # TqApi components (worker thread only)
        self.api: Optional[TqApi] = None
        self.redis_client: Optional[RedisClient] = None

        # Threading components
        self.order_queue = queue.Queue(maxsize=100)
        self.worker_thread: Optional[threading.Thread] = None
        self.worker_running = threading.Event()

        # Async components
        self.heartbeat_alive = False
        self.shutdown_event = asyncio.Event()

    def setup_logging(self):
        """Configure loguru logging"""
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>demo</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True
        )

    # === Worker Thread (Blocking) ===

    def tqapi_worker_loop(self):
        """
        TqApi blocking loop running in separate thread.
        Polls order queue and submits via TqApi.
        """
        logger.info("Worker thread starting...")

        try:
            # Initialize TqApi in this thread
            logger.info("Initializing TqApi in worker thread...")
            self.api = create_tqapi(self.config)
            self.redis_client = RedisClient(self.config)

            logger.info("Worker thread ready, entering wait_update() loop")
            block_counter = 0
            block_second = 10
            block_counter_max = 3


            def in_trading_time():
                """Check if current time is within trading hours:
                - 09:00:00 - 10:15:00
                - 10:30:00 - 11:30:00
                - 13:30:00 - 15:00:00
                """
                now_ts = pd.Timestamp.now(tz="Asia/Shanghai")
                hour = now_ts.hour
                minute = now_ts.minute
                time_in_minutes = hour * 60 + minute

                # Trading windows in minutes from midnight
                morning_session_1 = (9 * 60, 10 * 60 + 15)      # 09:00 - 10:15
                morning_session_2 = (10 * 60 + 30, 11 * 60 + 30)  # 10:30 - 11:30
                afternoon_session = (13 * 60 + 30, 15 * 60)      # 13:30 - 15:00

                return (morning_session_1[0] <= time_in_minutes <= morning_session_1[1] or
                        morning_session_2[0] <= time_in_minutes <= morning_session_2[1] or
                        afternoon_session[0] <= time_in_minutes <= afternoon_session[1])

            while self.worker_running.is_set():
                # Blocking call to TqApi
                logger.info(f"Call TqAPi Start! block_counter: {block_counter}")
                block_res = self.api.wait_update(deadline=time.time() + block_second)
                logger.info(f"Call TqAPi Finish! res: {block_res}, block_counter: {block_counter}")

                if not block_res:
                    if in_trading_time():
                        logger.info(f"Block in trading time, block_counter + 1")
                        block_counter += 1
                    else:
                        logger.info(f"Block not in trading time, skip")

                if block_counter > block_counter_max:
                    raise Exception("Too many Block, Close and Restart!")

                # Check for queued orders (non-blocking)
                try:
                    order_dict = self.order_queue.get_nowait()
                    logger.info(f"Processing order: {order_dict.get('order_id')}")
                    self._submit_order(order_dict)
                except queue.Empty:
                    pass  # No orders, continue loop
                except Exception as e:
                    logger.error(f"Error processing order: {e}")

        except Exception as e:
            logger.error(f"Fatal worker thread error: {e}", exc_info=True)
        finally:
            logger.info("Worker thread shutting down...")
            if self.api:
                close_tqapi(self.api)
            if self.redis_client:
                self.redis_client.close()

    def _submit_order(self, order_dict: dict):
        """Submit order via TqApi"""
        try:
            # Reuse existing logic from tq_order_submitter
            orders = split_close_order(
                order_dict,
                self.redis_client,
                self.config.portfolio_id
            )

            for order in orders:
                self.api.wait_update()
                execute_order(self.api, order)
                self.api.wait_update()

            logger.info(f"Order submitted: {order_dict.get('order_id')}")

        except Exception as e:
            logger.error(f"Error submitting order: {e}", exc_info=True)

    # === Async Tasks (Main Thread) ===

    async def consume_orders_async(self):
        """
        aio-pika consumer coroutine.
        Consumes orders and puts them in threading queue.
        """
        logger.info("Starting aio-pika consumer...")

        while not self.shutdown_event.is_set():
            try:
                # Robust connection with auto-reconnect
                connection = await aio_pika.connect_robust(
                    self.config.rabbitmq['url']
                )

                self.heartbeat_alive = True
                logger.info("aio-pika connected to RabbitMQ")

                async with connection:
                    channel = await connection.channel()
                    await channel.set_qos(prefetch_count=1)

                    # Declare exchange and queue
                    exchange = await channel.declare_exchange(
                        EXTERNAL_ORDER_EXCHANGE,
                        aio_pika.ExchangeType.TOPIC,
                        durable=True
                    )

                    queue_obj = await channel.declare_queue(
                        EXTERNAL_ORDER_SUBMIT_QUEUE,
                        durable=True
                    )

                    routing_key = f"PortfolioId_{self.config.portfolio_id}"
                    await queue_obj.bind(exchange, routing_key)

                    logger.info(f"Bound to queue: {EXTERNAL_ORDER_SUBMIT_QUEUE}, routing_key: {routing_key}")

                    # Consume messages
                    async with queue_obj.iterator() as queue_iter:
                        async for message in queue_iter:
                            async with message.process():
                                order_dict = json.loads(message.body)

                                # Put in thread-safe queue
                                try:
                                    self.order_queue.put_nowait(order_dict)
                                    logger.info(f"Queued order: {order_dict.get('order_id')}")
                                except queue.Full:
                                    logger.warning("Order queue full, dropping message")

                            if self.shutdown_event.is_set():
                                break

            except asyncio.CancelledError:
                logger.info("Consumer task cancelled")
                break
            except Exception as e:
                self.heartbeat_alive = False
                logger.error(f"Consumer error: {e}", exc_info=True)
                if not self.shutdown_event.is_set():
                    logger.info("Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)  # Retry delay

        logger.info("aio-pika consumer stopped")

    async def heartbeat_task(self):
        """Print heartbeat every second if aio-pika is alive"""
        logger.info("Starting heartbeat task...")

        while not self.shutdown_event.is_set():
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if self.heartbeat_alive:
                logger.info(f"[HEARTBEAT] {timestamp} - aio-pika alive")
            else:
                logger.warning(f"[HEARTBEAT] {timestamp} - aio-pika disconnected")

            if not self.worker_thread.is_alive():
                logger.error("TQSDK is Down, triggering shutdown!")
                self.shutdown_event.set()
                break

            await asyncio.sleep(1)

        logger.info("Heartbeat task stopped")

    async def start_async_tasks(self):
        """Start all async tasks"""
        consumer_task = asyncio.create_task(self.consume_orders_async())
        heartbeat = asyncio.create_task(self.heartbeat_task())

        # Wait for shutdown signal
        await self.shutdown_event.wait()

        # Cancel tasks
        consumer_task.cancel()
        heartbeat.cancel()

        await asyncio.gather(consumer_task, heartbeat, return_exceptions=True)

    # === Orchestration ===

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown()

    def shutdown(self):
        """Graceful shutdown of all components"""
        logger.info("Initiating shutdown...")

        # Stop async tasks
        self.shutdown_event.set()

        # Stop worker thread
        self.worker_running.clear()

        # Wait for worker thread
        if self.worker_thread and self.worker_thread.is_alive():
            logger.info("Waiting for worker thread...")
            self.worker_thread.join(timeout=5)

        logger.info("Shutdown complete")

    def run(self):
        """Main entry point"""
        self.setup_logging()

        logger.info("=" * 60)
        logger.info("Starting AioPika-TqApi Integration Demo")
        logger.info("=" * 60)

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            # Start worker thread
            self.worker_running.set()
            self.worker_thread = threading.Thread(
                target=self.tqapi_worker_loop,
                daemon=False
            )
            self.worker_thread.start()
            logger.info("Worker thread started")

            # Run async tasks in main thread
            asyncio.run(self.start_async_tasks())

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            self.shutdown()


if __name__ == "__main__":
    demo = AioPikaTqApiDemo()
    demo.run()
