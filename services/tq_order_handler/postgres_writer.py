"""
PostgreSQL writer for order updates
"""
import json
from typing import Dict, Any
from datetime import datetime
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

from shared.config import Config
from shared.models import OrderHistoryFuturesChn, TradeHistoryFuturesChn


class OrderPostgresWriter:
    """Writer for order updates to PostgreSQL using new schema"""

    def __init__(self, config: Config):
        self.config = config
        db_config = config.database
        db_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
        self.engine = create_engine(db_url, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine)
        logger.info("PostgreSQL connection established")

    def write_order_update(self, order_data: OrderHistoryFuturesChn) -> bool:
        """Write order update to database (only updates mutable fields)"""
        session = self.Session()
        try:
            # Update only fields that can change during order lifecycle
            update_sql = text("""
                UPDATE order_history_futures_chn
                SET
                    exchange_order_id = :exchange_order_id,
                    exchange_id = :exchange_id,
                    volume_left = :volume_left,
                    last_msg = :last_msg,
                    status = :status,
                    is_dead = :is_dead,
                    is_online = :is_online,
                    is_error = :is_error,
                    trade_price = :trade_price,
                    exchange_trading_date = :exchange_trading_date,
                    updated_at = NOW()
                WHERE order_id = :order_id
            """)

            session.execute(update_sql, {
                'order_id': order_data.order_id,
                'exchange_order_id': order_data.exchange_order_id,
                'exchange_id': order_data.exchange_id,
                'volume_left': order_data.volume_left,
                'last_msg': order_data.last_msg,
                'status': order_data.status,
                'is_dead': order_data.is_dead,
                'is_online': order_data.is_online,
                'is_error': order_data.is_error,
                'trade_price': order_data.trade_price,
                'exchange_trading_date': order_data.exchange_trading_date
            })

            # Process trade_records if present
            if order_data.trade_records:
                self._write_trade_records(session, order_data.order_id, order_data.trade_records, order_data.qpto_portfolio_id)

            session.commit()
            logger.debug(f"Order update written: {order_data.order_id} status={order_data.status}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to write order update: {e}")
            return False
        finally:
            session.close()

    def _write_trade_records(self, session, order_id: str, trade_records: Dict[str, Any], portfolio_id: str):
        """Write trade records to trade_history_futures_chn table"""
        try:
            for trade_id, trade_data in trade_records.items():
                # Check if trade already exists
                exists = session.execute(text("""
                    SELECT 1 FROM trade_history_futures_chn WHERE trade_id = :trade_id
                """), {'trade_id': trade_id}).fetchone()

                if exists:
                    logger.debug(f"Trade {trade_id} already exists, skipping")
                    continue

                # Create TradeHistoryFuturesChn object from dict
                trade = TradeHistoryFuturesChn(
                    trade_id=trade_id,
                    order_id=order_id,
                    exchange_trade_id=trade_data.get('exchange_trade_id', ''),
                    exchange_id=trade_data.get('exchange_id', ''),
                    instrument_id=trade_data.get('instrument_id', ''),
                    direction=trade_data.get('direction', ''),
                    offset=trade_data.get('offset', ''),
                    price=float(trade_data.get('price', 0)),
                    volume=int(trade_data.get('volume', 0)),
                    commission=float(trade_data.get('commission', 0)),
                    trade_date_time=int(trade_data.get('trade_date_time', 0)),
                    user_id=trade_data.get('user_id', ''),
                    seqno=int(trade_data.get('seqno', 0)),
                    qpto_portfolio_id=portfolio_id
                )

                insert_sql = text("""
                    INSERT INTO trade_history_futures_chn (
                        trade_id, order_id, exchange_trade_id, exchange_id, instrument_id,
                        direction, offset, price, volume, commission, trade_date_time,
                        user_id, seqno, qpto_portfolio_id
                    ) VALUES (
                        :trade_id, :order_id, :exchange_trade_id, :exchange_id, :instrument_id,
                        :direction, :offset, :price, :volume, :commission, :trade_date_time,
                        :user_id, :seqno, :qpto_portfolio_id
                    )
                """)

                session.execute(insert_sql, trade.to_dict())
                logger.debug(f"Trade record inserted: {trade_id}")

        except Exception as e:
            logger.error(f"Failed to write trade records: {e}")
            raise

    def close(self):
        """Close database connection"""
        self.engine.dispose()
        logger.info("PostgreSQL connection closed")
