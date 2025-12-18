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


class OrderPostgresWriter:
    """Writer for order updates to PostgreSQL"""

    def __init__(self, config: Config):
        self.config = config
        db_config = config.database
        db_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
        self.engine = create_engine(db_url, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine)
        logger.info("PostgreSQL connection established")

    def write_order_update(self, update: Dict[str, Any]) -> bool:
        """Write order update to database"""
        session = self.Session()
        try:
            order_id = update.get('order_id')
            status = update.get('status')
            event_type = update.get('event_type')
            filled_quantity = update.get('filled_quantity', 0)
            portfolio_id = update.get('portfolio_id')

            # Update order_history with smart status handling
            session.execute(text("""
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
                WHERE id = :order_id
            """), {
                'status': status,
                'filled_quantity': filled_quantity,
                'order_id': order_id
            })

            # Insert order event
            session.execute(text("""
                INSERT INTO order_event(id, status, msg, created_at, portfolio_id)
                VALUES (:order_id, :event_type, :msg, NOW(), :portfolio_id)
            """), {
                'order_id': order_id,
                'event_type': event_type,
                'msg': json.dumps(update),
                'portfolio_id': portfolio_id
            })

            session.commit()
            logger.debug(f"Order update written: {order_id} {event_type}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to write order update: {e}")
            return False
        finally:
            session.close()

    def close(self):
        """Close database connection"""
        self.engine.dispose()
        logger.info("PostgreSQL connection closed")
