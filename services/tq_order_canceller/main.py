#!/usr/bin/env python
"""
TQ Order Canceller Service

Consumes CANCEL order requests from external RabbitMQ and cancels via TqApi.
"""
import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from shared.aiopika_tqapi_base import AioPikaTqApiService
from shared.constants import EXTERNAL_ORDER_CANCEL_QUEUE, EXTERNAL_ORDER_EXCHANGE

from worker import process_order_cancel


class OrderCancellerService(AioPikaTqApiService):

    def get_queue_name(self) -> str:
        return EXTERNAL_ORDER_CANCEL_QUEUE

    def get_exchange_name(self) -> str:
        return EXTERNAL_ORDER_EXCHANGE

    def get_service_name(self) -> str:
        return "order_canceller"

    def initialize_worker_resources(self):
        pass

    def cleanup_worker_resources(self):
        pass

    def process_message_in_worker(self, message: dict) -> bool:
        return process_order_cancel(self.api, message)


if __name__ == "__main__":
    service = OrderCancellerService()
    service.run()
