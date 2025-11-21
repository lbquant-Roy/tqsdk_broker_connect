"""
Data processor for handling position and order updates
"""
import json
import redis
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from loguru import logger

from .config import Config


class DataProcessor:
    """Process and publish position and order updates"""

    CURRENT_POS_TTL = 3600  # 1 hour in seconds

    def __init__(self, config: Config):
        """
        Initialize data processor

        Parameters
        ----------
        config : Config
            Configuration instance
        """
        self.config = config

        # Initialize Redis connection
        redis_config = config.redis
        self.redis_client = redis.Redis(
            host=redis_config['host'],
            port=redis_config['port'],
            password=redis_config['password'],
            db=redis_config['db'],
            decode_responses=True
        )

        # Initialize database connection
        db_config = config.database
        db_url = (
            f"postgresql://{db_config['user']}:{db_config['password']}"
            f"@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
        )
        self.engine = create_engine(db_url, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine)

        logger.info("DataProcessor initialized")

    def process_position_update(self, symbol: str, position_amt: float):
        """
        Process position update and store in Redis

        Parameters
        ----------
        symbol : str
            Trading symbol
        position_amt : float
            Position amount (positive for long, negative for short)
        """
        try:
            redis_key = self.config.get_redis_position_key(symbol)
            self.redis_client.set(redis_key, position_amt, ex=self.CURRENT_POS_TTL)
            logger.debug(f"Position updated in Redis: {symbol} = {position_amt}")
        except Exception as e:
            logger.error(f"Failed to update position in Redis: {e}")

    def process_order_update(self, order_data: Dict[str, Any]):
        """
        Process order update and store in database

        Parameters
        ----------
        order_data : dict
            Order update data containing:
            - order_id: str
            - status: str
            - filled_quantity: float
            - avg_price: float (optional)
            - event_type: str (optional)
        """
        try:
            order_id = order_data.get('order_id')
            status = order_data.get('status')
            filled_quantity = order_data.get('filled_quantity', 0)

            with self.Session() as session:
                # Update order_history table
                update_sql = text("""
                    UPDATE order_history
                    SET status = CASE
                        WHEN status = 'PARTIALLY_FILLED' AND :status = 'CANCELED' THEN 'PARTIALLY_FILLED'
                        ELSE :status
                    END,
                    filled_quantity = CASE
                        WHEN :filled_quantity > filled_quantity THEN :filled_quantity
                        ELSE filled_quantity
                    END,
                    updated_at = NOW()
                    WHERE id = :id
                """)

                session.execute(update_sql, {
                    'id': order_id,
                    'status': status,
                    'filled_quantity': filled_quantity
                })

                # Insert order event
                insert_sql = text("""
                    INSERT INTO order_event(id, status, msg, created_at, portfolio_id)
                    VALUES (:id, :status, :msg, NOW(), :portfolio_id)
                """)

                session.execute(insert_sql, {
                    'id': order_id,
                    'status': order_data.get('event_type', status),
                    'msg': json.dumps(order_data),
                    'portfolio_id': self.config.portfolio_id
                })

                session.commit()

                logger.debug(f"Order updated in DB: {order_id} - {status}")

        except Exception as e:
            logger.error(f"Failed to update order in database: {e}")

    def get_current_positions(self) -> Dict[str, float]:
        """
        Get all current positions from Redis

        Returns
        -------
        dict
            Dictionary mapping symbols to position amounts
        """
        try:
            pattern = f"TQ_Position_PortfolioId_{self.config.portfolio_id}_Symbol_*"
            positions = {}

            for key in self.redis_client.scan_iter(match=pattern):
                symbol = key.split('_Symbol_')[-1]
                position = float(self.redis_client.get(key) or 0)
                positions[symbol] = position

            return positions
        except Exception as e:
            logger.error(f"Failed to get positions from Redis: {e}")
            return {}

    def store_account_info(self, account_data: Dict[str, Any]):
        """
        Store account information in Redis

        Parameters
        ----------
        account_data : dict
            Account data from TqApi
        """
        try:
            redis_key = f"TQ_Account_PortfolioId_{self.config.portfolio_id}"
            self.redis_client.setex(
                redis_key,
                self.CURRENT_POS_TTL,
                json.dumps(account_data)
            )
            logger.debug("Account info stored in Redis")
        except Exception as e:
            logger.error(f"Failed to store account info: {e}")

    def close(self):
        """Close connections"""
        try:
            self.redis_client.close()
            self.engine.dispose()
            logger.info("DataProcessor connections closed")
        except Exception as e:
            logger.error(f"Error closing DataProcessor: {e}")
