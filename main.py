#!/usr/bin/env python
"""
TqSDK Broker Connect - Main Entry Point

Separate TqAPI connection service that communicates with qpto_engine via RabbitMQ.
Handles order execution, position tracking, and account updates.
"""
import signal
import sys
import time
from typing import Optional
from loguru import logger

from tqsdk_client.config import get_config
from tqsdk_client.data_processor import DataProcessor
from tqsdk_client.tq_data_stream import TqDataStreamHandler
from tqsdk_client.order_executor import OrderExecutor
from tqsdk_client.connection_checker import check_all_connections


# Global instances for signal handling
data_processor: Optional[DataProcessor] = None
stream_handler: Optional[TqDataStreamHandler] = None
order_executor: Optional[OrderExecutor] = None


def setup_logging():
    """Setup logging configuration with loguru"""
    # Remove default handler
    logger.remove()

    # Add console handler with colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True
    )

    # Add file handler with rotation
    logger.add(
        "tqsdk_broker_connect.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        level="INFO",
        rotation="10 MB",
        retention="7 days",
        compression="zip"
    )


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")

    # Stop all components
    if order_executor:
        order_executor.stop()

    if stream_handler:
        stream_handler.stop()

    if data_processor:
        data_processor.close()

    logger.info("Shutdown complete")
    sys.exit(0)


def main():
    """Main entry point"""
    global data_processor, stream_handler, order_executor

    # Setup logging
    setup_logging()

    logger.info("=" * 60)
    logger.info("Starting TqSDK Broker Connect")
    logger.info("=" * 60)

    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = get_config()

        logger.info(f"Portfolio ID: {config.portfolio_id}")
        logger.info(f"Run Mode: {config.run_mode}")
        logger.info(f"Redis: {config.redis['host']}:{config.redis['port']}")
        logger.info(f"RabbitMQ: {config.rabbitmq['url']}")

        # Check all connections before initialization (5s timeout each)
        if not check_all_connections(config, timeout=5):
            logger.error("Connection checks failed. Please verify all services are running.")
            sys.exit(1)

        # Initialize components
        logger.info("Initializing data processor...")
        data_processor = DataProcessor(config)

        logger.info("Initializing TQ data stream handler...")
        stream_handler = TqDataStreamHandler(config, data_processor)

        logger.info("Initializing order executor...")
        order_executor = OrderExecutor(config, stream_handler)

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start TQ data stream (this will connect to TqApi)
        logger.info("Starting TQ data stream...")
        stream_handler.start()

        # Start order executor (this will start consuming from RabbitMQ)
        logger.info("Starting order executor...")
        order_executor.start()

        logger.info("=" * 60)
        logger.info("TqSDK Broker Connect is running")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)

        # Keep main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
