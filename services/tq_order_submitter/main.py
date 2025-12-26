#!/usr/bin/env python
"""
TQ Order Submitter Service

Consumes SUBMIT order requests from external RabbitMQ and executes via TqApi.
Handles CLOSETODAY splitting for SHFE/INE exchanges.
"""
import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from shared.aiopika_tqapi_base import AioPikaTqApiService
from shared.redis_client import RedisClient
from shared.constants import EXTERNAL_ORDER_SUBMIT_QUEUE, EXTERNAL_ORDER_EXCHANGE

from worker import process_order_submit


class OrderSubmitterService(AioPikaTqApiService):

    def __init__(self):
        super().__init__()
        self.redis_client = None

    def get_queue_name(self) -> str:
        return EXTERNAL_ORDER_SUBMIT_QUEUE

    def get_exchange_name(self) -> str:
        return EXTERNAL_ORDER_EXCHANGE

    def get_service_name(self) -> str:
        return "order_submitter"

    def initialize_worker_resources(self):
        self.redis_client = RedisClient(self.config)

    def cleanup_worker_resources(self):
        if self.redis_client:
            self.redis_client.close()

    def process_message_in_worker(self, message: dict) -> bool:
        return process_order_submit(self.api, self.redis_client, self.config, message)


if __name__ == "__main__":
    service = OrderSubmitterService()
    service.run()
