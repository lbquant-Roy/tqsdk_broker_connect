#!/bin/bash
#
# Wrapper script to convert TqSDK position snapshot to init pos format
#
# Usage:
#   ./run.sh [--snapshot TIMESTAMP] [--output FILE]
#
# Examples:
#   ./run.sh                                # Use latest snapshot, auto-generate filename
#   ./run.sh --snapshot 202601081530        # Use specific snapshot
#   ./run.sh --output my_pos.csv            # Custom output file
#   ./run.sh --snapshot 202601081530 --output my_pos.csv

# set -e

# SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# cd "$PROJECT_ROOT"
# uv run python scripts/update_init_pos/main.py "$@"

set -e

cd /workspaces/tqsdk_broker_connect

# Generate init pos from the latest snapshot
echo ""
echo "Generating init pos from latest snapshot..."
.venv/bin/python /workspaces/tqsdk_broker_connect/scripts/update_init_pos/main.py

# Sync to aliyun_2
echo ""
echo "Syncing init pos to aliyun_2..."
.venv/bin/python /workspaces/tqsdk_broker_connect/scripts/update_init_pos/sync_to_aliyun.py

echo ""
echo "Done! Data captured, init pos generated, and synced to aliyun_2."
