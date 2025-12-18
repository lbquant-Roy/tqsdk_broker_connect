# Deployment Configuration
# This file contains deployment parameters for different environments

# Aliyun ECS Configuration (optional - configure if deploying to Aliyun)
ALIYUN_HOST="139.196.123.105"
ALIYUN_USER="root"
ALIYUN_PORT=22

# Docker Image Configuration
# For multi-container architecture, each service has its own image
# Use build_all_images.sh to build all services
IMAGE_TAG="v0.2.0"
SAVE_DIR="/home/lbquant-roy"
REMOTE_DIR="/root"

# Build Configuration
BUILD_CONTEXT="../.."
