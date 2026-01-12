#!/usr/bin/env python3
"""
Sync latest init pos file to aliyun_2 server

Finds the most recently generated init_pos_YYYYMMDD.csv file and
syncs it to aliyun_2:/home/root/data/futures_backtest_input/init_pos.csv

Usage:
    python sync_to_aliyun.py [--host aliyun_2] [--remote-path PATH]
"""

import argparse
import subprocess
import sys
from pathlib import Path


def get_init_pos_dir() -> Path:
    """Get the directory for init pos files"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    return project_root / "data" / "init_pos"


def find_latest_init_pos() -> Path:
    """Find the latest init pos file"""
    init_pos_dir = get_init_pos_dir()

    if not init_pos_dir.exists():
        raise FileNotFoundError(f"Init pos directory not found: {init_pos_dir}")

    # Find all init_pos_*.csv files
    init_pos_files = sorted(init_pos_dir.glob("init_pos_*.csv"), reverse=True)

    if not init_pos_files:
        raise FileNotFoundError(f"No init pos files found in {init_pos_dir}")

    return init_pos_files[0]


def sync_to_remote(local_file: Path, remote_host: str, remote_path: str):
    """
    Sync local file to remote server using scp

    Args:
        local_file: Local file path
        remote_host: Remote host name (e.g., 'aliyun_2')
        remote_path: Remote file path
    """
    remote_target = f"{remote_host}:{remote_path}"

    print(f"Syncing {local_file.name} to {remote_target}...")

    # Use scp to copy the file
    cmd = ["scp", str(local_file), remote_target]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"Successfully synced to {remote_target}")
        else:
            print(f"Error: scp failed with return code {result.returncode}")
            if result.stderr:
                print(f"stderr: {result.stderr}")
            sys.exit(1)

    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to sync file to {remote_target}")
        print(f"Command: {' '.join(cmd)}")
        print(f"Return code: {e.returncode}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: scp command not found. Please ensure scp is installed.")
        sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Sync latest init pos file to aliyun_2 server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync to default location on aliyun_2
  python sync_to_aliyun.py

  # Sync to custom remote path
  python sync_to_aliyun.py --remote-path /custom/path/init_pos.csv

  # Sync to different host
  python sync_to_aliyun.py --host aliyun_3
        """
    )
    parser.add_argument(
        '--host',
        type=str,
        default='aliyun_2',
        help='Remote host name (default: aliyun_2)'
    )
    parser.add_argument(
        '--remote-path',
        type=str,
        default='/home/root/data/futures_backtest_input/init_pos.csv',
        help='Remote file path (default: /home/root/data/futures_backtest_input/init_pos.csv)'
    )

    args = parser.parse_args()

    try:
        # Find latest init pos file
        local_file = find_latest_init_pos()
        print(f"Found latest init pos file: {local_file}")

        # Sync to remote
        sync_to_remote(local_file, args.host, args.remote_path)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
