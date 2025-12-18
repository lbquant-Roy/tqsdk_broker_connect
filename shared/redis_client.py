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
    REDIS_POSITION_BREAKDOWN_KEY_PATTERN,
    REDIS_ACCOUNT_KEY_PATTERN,
    POSITION_TTL,
    POSITION_BREAKDOWN_TTL,
    ACCOUNT_TTL
)


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

    # Position operations
    def set_position(self, portfolio_id: str, symbol: str, value: float, ttl: int = POSITION_TTL):
        """Set position value in Redis"""
        key = REDIS_POSITION_KEY_PATTERN.format(portfolio_id=portfolio_id, symbol=symbol)
        try:
            self.client.setex(key, ttl, value)
            logger.debug(f"Position set: {key} = {value}")
        except Exception as e:
            logger.error(f"Failed to set position: {e}")
            raise

    def get_position(self, portfolio_id: str, symbol: str) -> Optional[float]:
        """Get position value from Redis"""
        key = REDIS_POSITION_KEY_PATTERN.format(portfolio_id=portfolio_id, symbol=symbol)
        try:
            value = self.client.get(key)
            return float(value) if value else None
        except Exception as e:
            logger.error(f"Failed to get position: {e}")
            return None

    # Position breakdown operations (for CLOSETODAY handling)
    def set_position_breakdown(self, portfolio_id: str, symbol: str, breakdown: Dict[str, Any],
                               ttl: int = POSITION_BREAKDOWN_TTL):
        """Set position breakdown in Redis"""
        key = REDIS_POSITION_BREAKDOWN_KEY_PATTERN.format(portfolio_id=portfolio_id, symbol=symbol)
        try:
            self.client.setex(key, ttl, json.dumps(breakdown))
            logger.debug(f"Position breakdown set: {key}")
        except Exception as e:
            logger.error(f"Failed to set position breakdown: {e}")
            raise

    def get_position_breakdown(self, portfolio_id: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position breakdown from Redis"""
        key = REDIS_POSITION_BREAKDOWN_KEY_PATTERN.format(portfolio_id=portfolio_id, symbol=symbol)
        try:
            value = self.client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Failed to get position breakdown: {e}")
            return None

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
