"""Send a few mock RabbitMQ messages for manual testing."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import uuid
from typing import Any, Dict
import time

from loguru import logger

from shared.config import get_config
from shared.constants import (
    EXTERNAL_ORDER_EXCHANGE,
    EXTERNAL_ORDER_SUBMIT_QUEUE,
    EXTERNAL_ORDER_CANCEL_QUEUE,
    INTERNAL_EXCHANGE,
    INTERNAL_ORDER_UPDATES_QUEUE,
    INTERNAL_ACCOUNT_UPDATES_QUEUE,
    ROUTING_KEY_ORDER_UPDATES,
    ROUTING_KEY_ACCOUNT_UPDATES,
)
from shared.rabbitmq_client import RabbitMQPublisher


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def declare_and_bind(publisher: RabbitMQPublisher, queue: str, exchange: str, routing_key: str) -> None:
    channel = publisher.channel
    if channel is None:
        raise RuntimeError("RabbitMQ channel not initialized")
    channel.queue_declare(queue=queue, durable=True)
    channel.queue_bind(exchange=exchange, queue=queue, routing_key=routing_key)


def submit_message(portfolio_id: str, order_id: str) -> Dict[str, Any]:
    return {
        "action": "SUBMIT",
        "symbol": "SHFE.pb2611",
        "direction": "SELL",
        "offset": "OPEN",
        "volume": 2,
        "limit_price": 17355,
        "order_id": order_id,
        "portfolio_id": portfolio_id,
        "timestamp": time.time_ns()
    }


def cancel_message(
    portfolio_id: str,
    order_id: str,
    cancel_type: str = "order_id",
    contract_code: str = "",
) -> Dict[str, Any]:
    return {
        "action": "CANCEL",
        "type": cancel_type,
        "order_id": order_id,
        "contract_code": contract_code,
        "portfolio_id": portfolio_id,
    }


def order_update_message(portfolio_id: str, order_id: str) -> Dict[str, Any]:
    return {
        "type": "ORDER_UPDATE",
        "timestamp": now_iso(),
        "portfolio_id": portfolio_id,
        "order_id": order_id,
        "symbol": "SHFE.rb2505",
        "direction": "BUY",
        "offset": "OPEN",
        "status": "FINISHED",
        "event_type": "COMPLETE_FILL",
        "volume_orign": 1,
        "volume_left": 0,
        "filled_quantity": 1,
        "limit_price": 3500.0,
        "trade_price": 3498.5,
    }


def account_update_message(portfolio_id: str) -> Dict[str, Any]:
    return {
        "type": "ACCOUNT_UPDATE",
        "timestamp": now_iso(),
        "portfolio_id": portfolio_id,
        "balance": 1_000_000.0,
        "available": 800_000.0,
        "margin": 200_000.0,
        "risk_ratio": 0.2,
        "position_profit": 12_345.67,
    }


def publish_external(
    publisher: RabbitMQPublisher,
    queue: str,
    routing_key: str,
    message: Dict[str, Any],
) -> None:
    declare_and_bind(publisher, queue, EXTERNAL_ORDER_EXCHANGE, routing_key)
    publisher.publish(routing_key=routing_key, message=message, exchange=EXTERNAL_ORDER_EXCHANGE)


def publish_internal(
    publisher: RabbitMQPublisher,
    queue: str,
    routing_key: str,
    message: Dict[str, Any],
) -> None:
    declare_and_bind(publisher, queue, INTERNAL_EXCHANGE, routing_key)
    publisher.publish(routing_key=routing_key, message=message, exchange=INTERNAL_EXCHANGE)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send mock RabbitMQ messages.")
    parser.add_argument(
        "--type",
        choices=("submit", "cancel", "order_update", "account_update", "all"),
        default="submit",
        help="Message type to publish.",
    )
    parser.add_argument(
        "--cancel-type",
        choices=("order_id", "contract_code"),
        default="order_id",
        help="Cancel message type to publish.",
    )
    parser.add_argument("--contract-code", default=None, help="Contract code override.")
    parser.add_argument("--order-id", default=None, help="Order ID override.")
    parser.add_argument("--portfolio-id", default=None, help="Portfolio ID override.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = get_config()
    portfolio_id = args.portfolio_id or config.portfolio_id
    order_id = args.order_id or f"mock-{uuid.uuid4().hex[:12]}"
    contract_code = args.contract_code or "SHFE.rb2605"
    routing_key = f"PortfolioId_{portfolio_id}"

    external = RabbitMQPublisher(config=config, exchange=EXTERNAL_ORDER_EXCHANGE, exchange_type="topic")
    internal = RabbitMQPublisher(config=config, exchange=INTERNAL_EXCHANGE, exchange_type="direct")

    try:
        external.connect()
        internal.connect()

        if args.type in ("submit", "all"):
            publish_external(
                external,
                EXTERNAL_ORDER_SUBMIT_QUEUE,
                routing_key,
                submit_message(portfolio_id, order_id),
            )
            logger.info(f"Published submit for order_id={order_id}")

        if args.type in ("cancel", "all"):
            publish_external(
                external,
                EXTERNAL_ORDER_CANCEL_QUEUE,
                routing_key,
                cancel_message(
                    portfolio_id,
                    order_id,
                    cancel_type=args.cancel_type,
                    contract_code=contract_code,
                ),
            )
            logger.info(f"Published cancel for order_id={order_id}")

        if args.type in ("order_update", "all"):
            publish_internal(
                internal,
                INTERNAL_ORDER_UPDATES_QUEUE,
                ROUTING_KEY_ORDER_UPDATES,
                order_update_message(portfolio_id, order_id),
            )
            logger.info(f"Published order update for order_id={order_id}")

        if args.type in ("account_update", "all"):
            publish_internal(
                internal,
                INTERNAL_ACCOUNT_UPDATES_QUEUE,
                ROUTING_KEY_ACCOUNT_UPDATES,
                account_update_message(portfolio_id),
            )
            logger.info("Published account update")

    finally:
        external.close()
        internal.close()


if __name__ == "__main__":
    main()
