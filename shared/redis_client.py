"""
Redis client helper for TqSDK Broker Connect services
"""
import json
from typing import Optional, Dict, Any
import redis
from loguru import logger

from .config import Config
from .constants import (
    REDIS_POSITION_KEY_PATTERN,
    REDIS_ACCOUNT_KEY_PATTERN,
    POSITION_TTL,
    ACCOUNT_TTL
)
from .models import FullPosition


class RedisClient:
    """Redis client for TqSDK Broker Connect services"""

    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[redis.Redis] = None
        self.connect()

    def connect(self):
        """Establish connection to Redis"""
        try:
            self.client = redis.Redis(
                host=self.config.redis['host'],
                port=self.config.redis['port'],
                password=self.config.redis.get('password'),
                db=self.config.redis.get('db', 0),
                decode_responses=True
            )
            self.client.ping()
            logger.info("Redis client connected")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    # Full position operations
    def set_full_position(self, portfolio_id: str, symbol: str, position: FullPosition,
                          ttl: int = POSITION_TTL):
        """Set full position dict in Redis with TTL"""
        key = REDIS_POSITION_KEY_PATTERN.format(portfolio_id=portfolio_id, symbol=symbol)
        try:
            self.client.setex(key, ttl, position.to_json())
            logger.debug(f"Full position set: {key} pos={position.pos}")
        except Exception as e:
            logger.error(f"Failed to set full position: {e}")
            raise

    def get_full_position(self, portfolio_id: str, symbol: str) -> Optional[FullPosition]:
        """Get full position dict from Redis"""
        key = REDIS_POSITION_KEY_PATTERN.format(portfolio_id=portfolio_id, symbol=symbol)
        try:
            value = self.client.get(key)
            return FullPosition.from_json(value) if value else None
        except Exception as e:
            logger.error(f"Failed to get full position: {e}")
            return None

    def refresh_position_ttl(self, portfolio_id: str, symbol: str, ttl: int = POSITION_TTL) -> bool:
        """Refresh TTL for existing position key"""
        key = REDIS_POSITION_KEY_PATTERN.format(portfolio_id=portfolio_id, symbol=symbol)
        try:
            return bool(self.client.expire(key, ttl))
        except Exception as e:
            logger.error(f"Failed to refresh position TTL: {e}")
            return False

    # Account operations
    def set_account(self, portfolio_id: str, account_data: Dict[str, Any], ttl: int = ACCOUNT_TTL):
        """Set account data in Redis"""
        key = REDIS_ACCOUNT_KEY_PATTERN.format(portfolio_id=portfolio_id)
        try:
            self.client.setex(key, ttl, json.dumps(account_data))
            logger.debug(f"Account data set: {key}")
        except Exception as e:
            logger.error(f"Failed to set account data: {e}")
            raise

    def get_account(self, portfolio_id: str) -> Optional[Dict[str, Any]]:
        """Get account data from Redis"""
        key = REDIS_ACCOUNT_KEY_PATTERN.format(portfolio_id=portfolio_id)
        try:
            value = self.client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Failed to get account data: {e}")
            return None

    def close(self):
        """Close Redis connection"""
        if self.client:
            try:
                self.client.close()
                logger.info("Redis client closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
