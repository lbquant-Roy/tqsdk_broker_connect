#!/bin/bash
# Capture TqSDK data snapshot, generate init pos, and sync to aliyun_2

set -e

cd /workspaces/tqsdk_broker_connect

# Capture data snapshot
.venv/bin/python /workspaces/tqsdk_broker_connect/scripts/capture_tqsdk_data/main.py