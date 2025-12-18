#!/bin/bash
# Build all Docker images for tqsdk_broker_connect multi-container architecture
# Usage: ./build_all_images.sh -e ENV
#   ENV options: local, cloud, aliyun

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/deploy_config.sh"

# Parse command line arguments
while getopts "e:" opt; do
  case $opt in
    e)
      ENV=$OPTARG
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      echo "Usage: $0 -e ENV"
      echo "  ENV options: local, cloud, aliyun"
      exit 1
      ;;
  esac
done

# Validate environment argument
if [ -z "$ENV" ]; then
  echo "Error: Environment argument required"
  echo "Usage: $0 -e ENV"
  echo "  ENV options: local, cloud, aliyun"
  exit 1
fi

# Services to build
SERVICES=(
  "order_submitter"
  "order_canceller"
  "order_monitor"
  "position_monitor"
  "account_monitor"
  "order_handler"
  "position_handler"
  "account_handler"
)

# Build each service
echo "========================================="
echo "Building all TqSDK Broker Connect images"
echo "Environment: $ENV"
echo "========================================="

for SERVICE in "${SERVICES[@]}"; do
  IMAGE_NAME="tq_${SERVICE}:$IMAGE_TAG"
  DOCKERFILE="Dockerfile.${SERVICE}"

  echo ""
  echo "Building $IMAGE_NAME..."
  docker build -t $IMAGE_NAME --build-context myapp=$BUILD_CONTEXT -f $DOCKERFILE .

  if [ $? -eq 0 ]; then
    echo "Successfully built $IMAGE_NAME"
  else
    echo "Failed to build $IMAGE_NAME"
    exit 1
  fi
done

echo ""
echo "========================================="
echo "All images built successfully!"
echo "========================================="

# List built images
echo ""
echo "Built images:"
for SERVICE in "${SERVICES[@]}"; do
  echo "  - tq_${SERVICE}:$IMAGE_TAG"
done

# If Aliyun environment, sync to remote server
if [ "$ENV" = "aliyun" ]; then
  if [ -f "$SCRIPT_DIR/sync_images_to_aliyun.sh" ]; then
    echo ""
    echo "Syncing images to Aliyun ECS..."
    "$SCRIPT_DIR/sync_images_to_aliyun.sh"
  else
    echo ""
    echo "Warning: sync_images_to_aliyun.sh not found. Skipping sync."
    echo "Images built successfully but not synced to Aliyun."
  fi
fi
