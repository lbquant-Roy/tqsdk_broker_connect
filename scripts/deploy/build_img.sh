#!/bin/bash
# Build Docker image for tqsdk_broker_connect
# Usage: ./build_img.sh -e ENV
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

# Set full image name
FULL_IMAGE_NAME="$IMAGE_NAME:$IMAGE_TAG"

# Set Dockerfile based on environment
if [ "$ENV" = "local" ]; then
  DOCKERFILE="Dockerfile.local"
  echo "Building image locally with $DOCKERFILE..."
elif [ "$ENV" = "cloud" ]; then
  DOCKERFILE="Dockerfile.cloud"
  echo "Building image for cloud with $DOCKERFILE..."
elif [ "$ENV" = "aliyun" ]; then
  # Build locally but push to Aliyun
  DOCKERFILE="Dockerfile.local"
  echo "Building image locally for Aliyun deployment..."

  # Validate Aliyun parameters from config
  if [ -z "$ALIYUN_HOST" ] || [ -z "$ALIYUN_USER" ] || [ "$ALIYUN_HOST" = "your_aliyun_host" ]; then
    echo "Error: Aliyun configuration incomplete in deploy_config.sh"
    echo "Please set ALIYUN_HOST and ALIYUN_USER in deploy_config.sh"
    exit 1
  fi
else
  echo "Invalid environment: $ENV"
  echo "Valid options: local, cloud, aliyun"
  exit 1
fi

# Build the Docker image
echo "Building $FULL_IMAGE_NAME..."
docker build -t $FULL_IMAGE_NAME --build-context myapp=$BUILD_CONTEXT -f $DOCKERFILE .

if [ $? -eq 0 ]; then
  echo "Successfully built $FULL_IMAGE_NAME"
else
  echo "Failed to build Docker image"
  exit 1
fi

# If Aliyun environment, sync to remote server
if [ "$ENV" = "aliyun" ]; then
  if [ -f "$SCRIPT_DIR/sync_image_to_aliyun.sh" ]; then
    echo "Syncing image to Aliyun ECS..."
    "$SCRIPT_DIR/sync_image_to_aliyun.sh"
  else
    echo "Warning: sync_image_to_aliyun.sh not found. Skipping sync."
    echo "Image built successfully but not synced to Aliyun."
  fi
fi
