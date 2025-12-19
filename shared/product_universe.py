"""
Product universe loader for main and next contract tracking.
Queries md_product_info and md_contract_info from PostgreSQL to get TqSDK symbols.
"""
import threading
from datetime import datetime
from typing import List, Optional

import psycopg2
from loguru import logger

from .config import Config
from .constants import UNIVERSE_REFRESH_INTERVAL_SECONDS


class ProductUniverseLoader:
    """Loads and caches main/next contract codes from md_product_info"""

    def __init__(self, config: Config, refresh_interval: int = UNIVERSE_REFRESH_INTERVAL_SECONDS):
        self.config = config
        self.refresh_interval = refresh_interval
        self._cache: List[str] = []
        self._last_refresh: Optional[datetime] = None
        self._lock = threading.Lock()

    def _get_connection(self):
        """Create PostgreSQL connection from config"""
        db = self.config.database
        return psycopg2.connect(
            host=db['host'],
            port=db['port'],
            user=db['user'],
            password=db['password'],
            dbname=db['dbname']
        )

    def load_universe(self) -> List[str]:
        """Load main and next contracts, return list of TqSDK symbols"""
        with self._lock:
            now = datetime.utcnow()
            if (self._last_refresh and
                    (now - self._last_refresh).total_seconds() < self.refresh_interval):
                return self._cache

            try:
                symbols = self._query_universe()
                self._cache = symbols
                self._last_refresh = now
                logger.info(f"Loaded {len(self._cache)} universe symbols from database")
                return self._cache
            except Exception as e:
                logger.error(f"Failed to load universe: {e}")
                # Return cached data if query fails
                return self._cache

    def _query_universe(self) -> List[str]:
        """Query database for main and next contract TqSDK codes"""
        query = """
            SELECT DISTINCT c.tqsdk_code
            FROM md_product_info p
            JOIN md_contract_info c ON p.current_main_contract_code = c.contract_code
            WHERE p.current_main_contract_code IS NOT NULL
              AND c.tqsdk_code IS NOT NULL
            UNION
            SELECT DISTINCT c.tqsdk_code
            FROM md_product_info p
            JOIN md_contract_info c ON p.next_main_contract_code = c.contract_code
            WHERE p.next_main_contract_code IS NOT NULL
              AND c.tqsdk_code IS NOT NULL
        """

        symbols = []
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query)
                for row in cursor.fetchall():
                    if row[0]:
                        symbols.append(row[0])
        finally:
            if conn:
                conn.close()

        return symbols

    def force_refresh(self) -> List[str]:
        """Force refresh of universe cache"""
        with self._lock:
            self._last_refresh = None
        return self.load_universe()
