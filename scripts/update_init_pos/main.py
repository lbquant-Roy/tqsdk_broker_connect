#!/usr/bin/env python3
"""
Convert TqSDK position snapshot data to init pos format

Reads positions.json from tqsdk_api_snapshot directory and generates
init pos CSV file with the same format as convert_gui_pos_to_init_pos.py

Output format: CSV with columns [symbol, position]
  - symbol: {exchange}_{product} (e.g., CZCE_AP)
  - position: net position (positive=long, negative=short)

Usage:
    python main.py [--snapshot YYYYMMDDHHMM] [--output FILE]

    # Use latest snapshot, auto-generate output filename
    python main.py

    # Use specific snapshot, auto-generate output filename
    python main.py --snapshot 202601081530

    # Custom output file
    python main.py --snapshot 202601081530 --output my_pos.csv
"""

import sys
import json
import re
import argparse
from pathlib import Path
import pandas as pd


def map_exchange_id(tqsdk_exchange: str) -> str:
    """
    Map TqSDK exchange ID to qpto_engine exchange ID

    TqSDK uses: CZCE, SHFE, DCE, INE, CFFEX, GFEX
    qpto_engine uses: XZCE, XSGE, XDCE, XINE, CCFX, GFEX

    Args:
        tqsdk_exchange: TqSDK exchange ID (e.g., 'CZCE', 'SHFE')

    Returns:
        qpto_engine exchange ID (e.g., 'XZCE', 'XSGE')
    """
    exchange_map = {
        'CZCE': 'XZCE',
        'SHFE': 'XSGE',
        'DCE': 'XDCE',
        'INE': 'XINE',
        'CFFEX': 'CCFX',
        'GFEX': 'GFEX'
    }
    return exchange_map.get(tqsdk_exchange, tqsdk_exchange)


def extract_product_code(instrument_id: str) -> str:
    """
    Extract product code from instrument ID

    Examples:
        AP605 -> AP
        m2505 -> M
        rb2505 -> RB
        au2505 -> AU

    Args:
        instrument_id: Instrument ID like 'AP605', 'm2505', 'rb2505'

    Returns:
        Product code in uppercase (e.g., 'AP', 'M', 'RB', 'AU')
    """
    match = re.match(r'([a-zA-Z]+)', instrument_id)
    if not match:
        return None
    return match.group(1).upper()


def get_snapshot_base_dir() -> Path:
    """Get the base directory for snapshots"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    return project_root / "data" / "tqsdk_api_snapshot"


def get_init_pos_dir() -> Path:
    """Get the directory for init pos files"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    return project_root / "data" / "init_pos"


def find_latest_snapshot(snapshot_base_dir: Path) -> Path:
    """Find the latest snapshot directory"""
    snapshot_dirs = sorted([d for d in snapshot_base_dir.glob("202*") if d.is_dir()], reverse=True)

    if not snapshot_dirs:
        raise FileNotFoundError(f"No snapshot directories found in {snapshot_base_dir}")

    return snapshot_dirs[0]


def get_snapshot_dir(snapshot_timestamp: str = None) -> tuple[Path, str]:
    """
    Get snapshot directory and timestamp

    Args:
        snapshot_timestamp: Optional snapshot timestamp (YYYYMMDDHHMM)

    Returns:
        Tuple of (snapshot_dir, snapshot_timestamp)
    """
    snapshot_base_dir = get_snapshot_base_dir()

    if snapshot_timestamp:
        snapshot_dir = snapshot_base_dir / snapshot_timestamp
        if not snapshot_dir.exists():
            raise FileNotFoundError(f"Snapshot directory not found: {snapshot_dir}")
    else:
        snapshot_dir = find_latest_snapshot(snapshot_base_dir)
        snapshot_timestamp = snapshot_dir.name
        print(f"Using latest snapshot: {snapshot_timestamp}")

    return snapshot_dir, snapshot_timestamp


def generate_output_filename(snapshot_timestamp: str) -> Path:
    """
    Generate output filename from snapshot timestamp

    Args:
        snapshot_timestamp: Snapshot timestamp (YYYYMMDDHHMM)

    Returns:
        Output file path
    """
    # Extract date from timestamp (YYYYMMDDHHMM -> YYYYMMDD)
    snapshot_date = snapshot_timestamp[:8]

    init_pos_dir = get_init_pos_dir()
    init_pos_dir.mkdir(parents=True, exist_ok=True)

    return init_pos_dir / f"init_pos_{snapshot_date}.csv"


def load_position_snapshot(snapshot_dir: Path) -> dict:
    """Load positions.json from snapshot directory"""
    positions_file = snapshot_dir / "positions.json"

    if not positions_file.exists():
        raise FileNotFoundError(f"Positions file not found: {positions_file}")

    with open(positions_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def convert_snapshot_to_init_pos(snapshot_dir: Path, output_file: Path):
    """
    Convert tqsdk position snapshot to init pos format

    Args:
        snapshot_dir: Directory containing positions.json
        output_file: Output CSV file path
    """
    print(f"Reading positions from: {snapshot_dir}")

    # Load positions data
    positions_data = load_position_snapshot(snapshot_dir)

    results = []

    for contract_key, position_info in positions_data.items():
        # Skip if no position
        pos = position_info.get('pos', 0)
        if pos == 0:
            continue

        # Extract exchange and instrument
        exchange_id = position_info.get('exchange_id', '')
        instrument_id = position_info.get('instrument_id', '')

        if not exchange_id or not instrument_id:
            print(f"Warning: Missing exchange_id or instrument_id for {contract_key}, skipping")
            continue

        # Extract product code
        product = extract_product_code(instrument_id)
        if not product:
            print(f"Warning: Could not extract product from {instrument_id}, skipping")
            continue

        # Map TqSDK exchange to qpto_engine exchange
        mapped_exchange = map_exchange_id(exchange_id)

        # Format symbol as {exchange}_{product}
        symbol = f"{mapped_exchange}_{product}"

        # Position is already signed (positive=long, negative=short)
        position = int(pos)

        results.append({
            'symbol': symbol,
            'position': position
        })

        # Print conversion info (similar to GUI converter)
        direction = "买" if position > 0 else "卖"
        print(f"{contract_key} ({direction}) -> {symbol}: {position}")

    # Save output
    if not results:
        print("Warning: No positions found!")
        output_df = pd.DataFrame(columns=['symbol', 'position'])
    else:
        output_df = pd.DataFrame(results)
        # Sort by symbol for consistent output
        output_df = output_df.sort_values('symbol').reset_index(drop=True)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_file, index=False)
    print(f"\nSaved {len(output_df)} positions to {output_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Convert TqSDK position snapshot to init pos format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use latest snapshot, auto-generate output filename
  python main.py

  # Use specific snapshot, auto-generate output filename
  python main.py --snapshot 202601081530

  # Custom output file
  python main.py --snapshot 202601081530 --output my_pos.csv

  # Legacy usage (still supported)
  python main.py /path/to/snapshot output.csv
        """
    )
    parser.add_argument(
        '--snapshot',
        type=str,
        help='Snapshot timestamp (YYYYMMDDHHMM). If not specified, uses latest snapshot.'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output CSV file path. If not specified, auto-generates based on snapshot date.'
    )
    # Legacy positional arguments
    parser.add_argument(
        'legacy_snapshot_dir',
        nargs='?',
        type=str,
        help=argparse.SUPPRESS  # Hide from help
    )
    parser.add_argument(
        'legacy_output_file',
        nargs='?',
        type=str,
        help=argparse.SUPPRESS  # Hide from help
    )

    args = parser.parse_args()

    try:
        # Check if using legacy positional arguments
        if args.legacy_snapshot_dir and args.legacy_output_file:
            snapshot_dir = Path(args.legacy_snapshot_dir)
            output_file = Path(args.legacy_output_file)
            if not snapshot_dir.exists():
                print(f"Error: Snapshot directory does not exist: {snapshot_dir}")
                sys.exit(1)
        else:
            # New argument style
            snapshot_dir, snapshot_timestamp = get_snapshot_dir(args.snapshot)

            if args.output:
                output_file = Path(args.output)
            else:
                output_file = generate_output_filename(snapshot_timestamp)

        convert_snapshot_to_init_pos(snapshot_dir, output_file)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
