#!/bin/bash
# Build unified Docker image for tqsdk_broker_connect multi-container architecture
# This replaces the old build_all_images.sh that built 8 separate images
#
# Usage: ./build_unified_image.sh [-v VERSION]
#   VERSION: optional image tag (default from deploy_config.sh)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/deploy_config.sh"

# Default values
VERSION="${IMAGE_TAG}"

# Parse arguments
while getopts "v:h" opt; do
  case $opt in
    v) VERSION=$OPTARG ;;
    h)
      echo "Usage: $0 [-v VERSION]"
      echo ""
      echo "Arguments:"
      echo "  -v VERSION  Image version tag (default: $IMAGE_TAG)"
      echo "  -h          Show this help message"
      echo ""
      echo "Examples:"
      echo "  $0                    # Build with default version"
      echo "  $0 -v v0.3.0          # Build with custom version"
      exit 0
      ;;
    \?)
      echo "Error: Invalid option -$OPTARG" >&2
      echo "Run '$0 -h' for help"
      exit 1
      ;;
  esac
done

# Image configuration
IMAGE_NAME="tqsdk_broker_connect"
IMAGE_TAG_FULL="${IMAGE_NAME}:${VERSION}"

echo "========================================"
echo "Building Unified TqSDK Broker Connect Image"
echo "========================================"
echo "Version:       $VERSION"
echo "Image:         $IMAGE_TAG_FULL"
echo "Build context: $BUILD_CONTEXT"
echo "========================================"
echo ""

# Build unified image
echo "Building Docker image..."
docker build \
  -t "$IMAGE_TAG_FULL" \
  --build-context myapp="$BUILD_CONTEXT" \
  -f Dockerfile \
  .

if [ $? -eq 0 ]; then
  echo ""
  echo "========================================"
  echo "Build Successful!"
  echo "========================================"
  echo "Image: $IMAGE_TAG_FULL"
  echo ""
  echo "Next steps:"
  echo ""
  echo "  Test locally:"
  echo "    cd tqsdk_broker_connect"
  echo "    docker-compose up -d"
  echo ""
  echo "  Push to Aliyun ACR:"
  echo "    ./push_to_acr.sh -v $VERSION"
  echo "========================================"
  exit 0
else
  echo ""
  echo "========================================"
  echo "Build Failed!"
  echo "========================================"
  exit 1
fi
