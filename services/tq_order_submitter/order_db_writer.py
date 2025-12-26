"""
Database writer for order insertion (submit service)
"""
from typing import Dict, Any
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from shared.config import Config
from shared.models import OrderHistoryFuturesChn


class OrderDbWriter:
    """Writer for order insertion with connection pooling"""

    def __init__(self, config: Config):
        self.config = config
        db_config = config.database
        db_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
        self.engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600
        )
        self.Session = sessionmaker(bind=self.engine)
        logger.info("OrderDbWriter initialized with connection pool")

    def insert_order(self, order_data: OrderHistoryFuturesChn) -> bool:
        """Insert new order into database"""
        session = self.Session()
        try:
            insert_sql = text("""
                INSERT INTO order_history_futures_chn (
                    order_id, exchange_order_id, exchange_id, instrument_id,
                    direction, order_offset, volume_orign, volume_left, limit_price,
                    price_type, volume_condition, time_condition, insert_date_time,
                    last_msg, status, is_dead, is_online, is_error, trade_price,
                    qpto_portfolio_id, qpto_contract_code, sender_type,
                    qpto_order_tag, qpto_trading_date, exchange_trading_date,
                    origin_timestamp
                ) VALUES (
                    :order_id, :exchange_order_id, :exchange_id, :instrument_id,
                    :direction, :order_offset, :volume_orign, :volume_left, :limit_price,
                    :price_type, :volume_condition, :time_condition, :insert_date_time,
                    :last_msg, :status, :is_dead, :is_online, :is_error, :trade_price,
                    :qpto_portfolio_id, :qpto_contract_code, :sender_type,
                    :qpto_order_tag, :qpto_trading_date, :exchange_trading_date,
                    :origin_timestamp
                )
            """)

            order_dict = order_data.to_dict()
            # Remove trade_records from dict as it's not a table column
            order_dict.pop('trade_records', None)
            session.execute(insert_sql, order_dict)

            session.commit()
            logger.debug(f"Order inserted to DB: {order_data.order_id}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to insert order to DB: {e}")
            return False
        finally:
            session.close()

    def close(self):
        """Close database connection pool"""
        self.engine.dispose()
        logger.info("OrderDbWriter connection pool closed")
