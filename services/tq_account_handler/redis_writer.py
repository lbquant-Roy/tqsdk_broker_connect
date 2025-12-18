"""
Redis writer for account updates
"""
from typing import Dict, Any
from loguru import logger

import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from shared.redis_client import RedisClient


class AccountRedisWriter:
    """Writer for account updates to Redis"""

    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client

    def write_account_update(self, update: Dict[str, Any]) -> bool:
        """Write account update to Redis"""
        try:
            portfolio_id = update.get('portfolio_id')
            account_data = {
                'balance': update.get('balance', 0),
                'available': update.get('available', 0),
                'margin': update.get('margin', 0),
                'risk_ratio': update.get('risk_ratio', 0),
                'position_profit': update.get('position_profit', 0)
            }

            self.redis_client.set_account(portfolio_id, account_data)
            logger.debug(f"Account written: balance={account_data['balance']:.2f}")
            return True

        except Exception as e:
            logger.error(f"Failed to write account: {e}")
            return False
