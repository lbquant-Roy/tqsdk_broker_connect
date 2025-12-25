#!/usr/bin/env python3
"""
TqSDK Data Capture Script

Captures all TqSDK response data types (account, positions, orders, trades, quotes, klines)
and saves each to separate JSON files for demo data review.

Usage:
    cd /workspaces/tqsdk_broker_connect
    uv run python scripts/capture_tqsdk_data.py
"""

import sys
sys.path.insert(0, '/workspaces/tqsdk_broker_connect')

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from loguru import logger
from tqsdk import TqApi
from tqsdk.entity import Entity

from shared.config import get_config
from shared.tqapi_factory import create_tqapi, close_tqapi

# Constants
DEMO_SYMBOLS = ["SHFE.rb2505", "DCE.m2505", "SHFE.au2505"]
KLINE_DURATIONS = [60, 300, 3600, 86400]
KLINE_DATA_LENGTH = 100
UPDATE_ITERATIONS = 30
OUTPUT_DIR = Path("/workspaces/tqsdk_broker_connect/demo_data")


class TqSDKEncoder(json.JSONEncoder):
    """Custom JSON encoder for TqSDK objects"""

    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj) if not np.isnan(obj) else None
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if isinstance(obj, Entity):
            return entity_to_dict(obj)
        return super().default(obj)


def entity_to_dict(entity: Entity) -> Dict[str, Any]:
    """
    Convert TqSDK Entity to dict, recursively handling nested entities

    Args:
        entity: TqSDK Entity object (Account, Position, Order, etc.)

    Returns:
        Dictionary representation with private fields filtered out
    """
    result = {}

    for key in dir(entity):
        if key.startswith('_'):
            continue

        if key in ['items', 'keys', 'values', 'get', 'update', 'clear', 'pop', 'popitem', 'setdefault']:
            continue

        try:
            value = getattr(entity, key)

            if callable(value):
                continue

            if isinstance(value, Entity):
                result[key] = entity_to_dict(value)
            elif isinstance(value, dict):
                result[key] = {
                    k: entity_to_dict(v) if isinstance(v, Entity) else v
                    for k, v in value.items()
                    if not k.startswith('_')
                }
            elif isinstance(value, list):
                result[key] = [
                    entity_to_dict(item) if isinstance(item, Entity) else item
                    for item in value
                ]
            else:
                result[key] = value
        except Exception as e:
            logger.warning(f"Failed to get attribute {key} from entity: {e}")
            continue

    return result


def serialize_dataframe(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Convert pandas DataFrame to JSON-serializable list of dicts

    Handles numpy types, NaN values, and timestamps

    Args:
        df: pandas DataFrame (typically kline data)

    Returns:
        List of dictionaries with clean Python native types
    """
    records = df.to_dict('records')

    serialized = []
    for record in records:
        clean_record = {}
        for key, value in record.items():
            if isinstance(value, (np.integer, np.int64)):
                clean_record[key] = int(value)
            elif isinstance(value, (np.floating, np.float64)):
                clean_record[key] = float(value) if not np.isnan(value) else None
            elif isinstance(value, pd.Timestamp):
                clean_record[key] = value.isoformat()
            else:
                clean_record[key] = value
        serialized.append(clean_record)

    return serialized


def capture_account(api: TqApi) -> Dict[str, Any]:
    """Capture account data"""
    try:
        account = api.get_account()
        return entity_to_dict(account)
    except Exception as e:
        logger.error(f"Error capturing account: {e}")
        return {"error": str(e)}


def capture_positions(api: TqApi) -> Dict[str, Any]:
    """Capture all positions"""
    try:
        positions = api.get_position()
        result = {}
        for symbol, position in positions.items():
            if not symbol.startswith("_"):
                result[symbol] = entity_to_dict(position)
        return result
    except Exception as e:
        logger.error(f"Error capturing positions: {e}")
        return {"error": str(e)}


def capture_orders(api: TqApi) -> Dict[str, Any]:
    """Capture all orders"""
    try:
        orders = api.get_order()
        result = {}
        for order_id, order in orders.items():
            if not order_id.startswith("_"):
                result[order_id] = entity_to_dict(order)
        return result
    except Exception as e:
        logger.error(f"Error capturing orders: {e}")
        return {"error": str(e)}


def capture_trades(api: TqApi) -> Dict[str, Any]:
    """Capture all trades"""
    try:
        trades = api.get_trade()
        result = {}
        for trade_id, trade in trades.items():
            if not trade_id.startswith("_"):
                result[trade_id] = entity_to_dict(trade)
        return result
    except Exception as e:
        logger.error(f"Error capturing trades: {e}")
        return {"error": str(e)}


def capture_quotes(api: TqApi, symbols: List[str]) -> Dict[str, Any]:
    """Capture quote data for specified symbols"""
    quotes = {}
    for symbol in symbols:
        try:
            quote = api.get_quote(symbol)
            quotes[symbol] = entity_to_dict(quote)
        except Exception as e:
            logger.error(f"Error capturing quote for {symbol}: {e}")
            quotes[symbol] = {"error": str(e)}
    return quotes


def capture_klines(api: TqApi, symbols: List[str], durations: List[int]) -> Dict[str, Any]:
    """Capture kline data for symbols and durations"""
    klines = {}
    for symbol in symbols:
        klines[symbol] = {}
        for duration in durations:
            try:
                df = api.get_kline_serial(symbol, duration, KLINE_DATA_LENGTH)
                klines[symbol][f"{duration}s"] = serialize_dataframe(df)
            except Exception as e:
                logger.error(f"Error capturing kline {symbol}/{duration}s: {e}")
                klines[symbol][f"{duration}s"] = {"error": str(e)}
    return klines


def save_json(data: Any, filepath: Path, pretty: bool = True):
    """Save data to JSON file with error handling"""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(data, f, cls=TqSDKEncoder, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, cls=TqSDKEncoder, ensure_ascii=False)

        logger.info(f"Saved {filepath.name}")
    except Exception as e:
        logger.error(f"Error saving {filepath}: {e}")


def create_metadata(config, symbols: List[str], durations: List[int]) -> Dict[str, Any]:
    """Create metadata about the capture"""
    return {
        "capture_timestamp": datetime.now().isoformat(),
        "tq_username": config.tq_username,
        "portfolio_id": config.portfolio_id,
        "run_mode": config.run_mode,
        "symbols": symbols,
        "kline_durations": durations,
        "kline_data_length": KLINE_DATA_LENGTH,
        "update_iterations": UPDATE_ITERATIONS,
        "script_version": "1.0.0"
    }


def main():
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("TqSDK Data Capture Script - Starting")
    logger.info("=" * 60)

    config = get_config()
    OUTPUT_DIR.mkdir(exist_ok=True)
    api = None

    try:
        logger.info("Initializing TqApi...")
        api = create_tqapi(config)
        logger.info("TqApi initialized successfully")

        logger.info(f"Subscribing to symbols: {DEMO_SYMBOLS}")
        for symbol in DEMO_SYMBOLS:
            api.get_quote(symbol)
            for duration in KLINE_DURATIONS:
                api.get_kline_serial(symbol, duration, KLINE_DATA_LENGTH)

        logger.info(f"Waiting for data updates ({UPDATE_ITERATIONS} iterations)...")
        for i in range(UPDATE_ITERATIONS):
            api.wait_update(deadline=2)
            if i % 10 == 0:
                logger.info(f"Update iteration {i}/{UPDATE_ITERATIONS}")

        logger.info("Data updates complete")
        logger.info("-" * 60)

        logger.info("Capturing account data...")
        account_data = capture_account(api)

        logger.info("Capturing positions...")
        positions_data = capture_positions(api)

        logger.info("Capturing orders...")
        orders_data = capture_orders(api)

        logger.info("Capturing trades...")
        trades_data = capture_trades(api)

        logger.info("Capturing quotes...")
        quotes_data = capture_quotes(api, DEMO_SYMBOLS)

        logger.info("Capturing klines...")
        klines_data = capture_klines(api, DEMO_SYMBOLS, KLINE_DURATIONS)

        logger.info("-" * 60)
        logger.info("Saving data to files...")

        save_json(account_data, OUTPUT_DIR / "account.json")
        save_json(positions_data, OUTPUT_DIR / "positions.json")
        save_json(orders_data, OUTPUT_DIR / "orders.json")
        save_json(trades_data, OUTPUT_DIR / "trades.json")
        save_json(quotes_data, OUTPUT_DIR / "quotes.json")
        save_json(klines_data, OUTPUT_DIR / "klines.json")

        metadata = create_metadata(config, DEMO_SYMBOLS, KLINE_DURATIONS)
        save_json(metadata, OUTPUT_DIR / "capture_metadata.json")

        logger.info("=" * 60)
        logger.info(f"Data capture complete! Files saved to {OUTPUT_DIR}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error during data capture: {e}", exc_info=True)
        raise
    finally:
        if api:
            logger.info("Closing TqApi...")
            close_tqapi(api)
            logger.info("TqApi closed")


if __name__ == "__main__":
    main()
