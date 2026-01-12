#!/bin/bash
#
# Wrapper script to sync latest init pos to aliyun_2
#
# Usage:
#   ./sync.sh [--host HOST] [--remote-path PATH]
#
# Examples:
#   ./sync.sh                                # Sync to aliyun_2 (default)
#   ./sync.sh --host aliyun_3                # Sync to aliyun_3
#   ./sync.sh --remote-path /custom/init_pos.csv

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"
uv run python scripts/update_init_pos/sync_to_aliyun.py "$@"
