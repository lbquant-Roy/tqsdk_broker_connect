# Deployment Configuration
# This file contains deployment parameters for different environments

# Aliyun ECS Configuration (optional - configure if deploying to Aliyun)
ALIYUN_HOST="139.196.123.105"
ALIYUN_USER="root"
ALIYUN_PORT=22

# Aliyun ACR Configuration
ACR_REGISTRY="acr-sh-1-registry.cn-shanghai.cr.aliyuncs.com"
ACR_NAMESPACE="qpto"
ACR_IMAGE_NAME="tqsdk_broker_connect"

# Docker Image Configuration
# Unified image for all 8 services (command override in docker-compose)
IMAGE_TAG="v0.3.5"

# Build Configuration
BUILD_CONTEXT="../.."

# Deprecated (no longer used with unified image)
# SAVE_DIR="/home/lbquant-roy"
# REMOTE_DIR="/root"
