#!/bin/bash
# Push unified Docker image to Aliyun Container Registry (ACR)
#
# Usage: ./push_to_acr.sh -v VERSION [-l]
#   -v VERSION: Image version tag (required)
#   -l: Also tag and push as 'latest'

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/deploy_config.sh"

# Aliyun ACR configuration
ACR_REGISTRY="${ACR_REGISTRY:-acr-sh-1-registry.cn-shanghai.cr.aliyuncs.com}"
ACR_NAMESPACE="${ACR_NAMESPACE:-qpto}"
ACR_IMAGE_NAME="${ACR_IMAGE_NAME:-tqsdk_broker_connect}"

# Parse arguments
VERSION=""
TAG_LATEST=false

while getopts "v:lh" opt; do
  case $opt in
    v) VERSION=$OPTARG ;;
    l) TAG_LATEST=true ;;
    h)
      echo "Usage: $0 -v VERSION [-l]"
      echo ""
      echo "Arguments:"
      echo "  -v VERSION  Image version tag (required, e.g., v0.3.0)"
      echo "  -l          Also tag and push as 'latest'"
      echo "  -h          Show this help message"
      echo ""
      echo "Examples:"
      echo "  $0 -v v0.3.0      # Push versioned tag only"
      echo "  $0 -v v0.3.0 -l   # Push versioned tag and latest"
      exit 0
      ;;
    \?)
      echo "Error: Invalid option -$OPTARG" >&2
      echo "Run '$0 -h' for help"
      exit 1
      ;;
  esac
done

# Validate version
if [ -z "$VERSION" ]; then
  echo "Error: Version required (-v VERSION)"
  echo "Run '$0 -h' for help"
  exit 1
fi

# Image names
LOCAL_IMAGE="tqsdk_broker_connect:${VERSION}"
ACR_IMAGE="${ACR_REGISTRY}/${ACR_NAMESPACE}/${ACR_IMAGE_NAME}"
ACR_IMAGE_VERSIONED="${ACR_IMAGE}:${VERSION}"
ACR_IMAGE_LATEST="${ACR_IMAGE}:latest"

echo "========================================"
echo "Pushing to Aliyun ACR"
echo "========================================"
echo "Local image:    $LOCAL_IMAGE"
echo "ACR registry:   $ACR_REGISTRY"
echo "ACR namespace:  $ACR_NAMESPACE"
echo "ACR image:      $ACR_IMAGE_VERSIONED"
if [ "$TAG_LATEST" = true ]; then
  echo "Latest tag:     $ACR_IMAGE_LATEST"
fi
echo "========================================"
echo ""

# Check if local image exists
if ! docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${LOCAL_IMAGE}$"; then
  echo "Error: Local image '$LOCAL_IMAGE' not found"
  echo ""
  echo "Build it first:"
  echo "  ./build_unified_image.sh -e cloud -v $VERSION"
  exit 1
fi

# Login to ACR (interactive)
echo "Logging in to Aliyun ACR..."
echo "Tip: Use your Aliyun account credentials"
echo "Command: docker login --username=<your-aliyun-account> $ACR_REGISTRY"
echo ""

docker login "$ACR_REGISTRY"

if [ $? -ne 0 ]; then
  echo ""
  echo "Error: ACR login failed"
  exit 1
fi

# Tag for ACR
echo ""
echo "Tagging image for ACR..."
docker tag "$LOCAL_IMAGE" "$ACR_IMAGE_VERSIONED"

if [ "$TAG_LATEST" = true ]; then
  echo "Tagging as latest..."
  docker tag "$LOCAL_IMAGE" "$ACR_IMAGE_LATEST"
fi

# Push versioned tag
echo ""
echo "Pushing $ACR_IMAGE_VERSIONED..."
docker push "$ACR_IMAGE_VERSIONED"

if [ $? -ne 0 ]; then
  echo ""
  echo "Error: Push failed"
  exit 1
fi

# Push latest tag if requested
if [ "$TAG_LATEST" = true ]; then
  echo ""
  echo "Pushing $ACR_IMAGE_LATEST..."
  docker push "$ACR_IMAGE_LATEST"

  if [ $? -ne 0 ]; then
    echo ""
    echo "Error: Latest tag push failed"
    exit 1
  fi
fi

echo ""
echo "========================================"
echo "Push Successful!"
echo "========================================"
echo "Pushed images:"
echo "  - $ACR_IMAGE_VERSIONED"
if [ "$TAG_LATEST" = true ]; then
  echo "  - $ACR_IMAGE_LATEST"
fi
echo ""
echo "Pull command for cloud deployment:"
echo "  docker pull $ACR_IMAGE_VERSIONED"
echo ""
echo "Or use in docker-compose.yml:"
echo "  export REGISTRY=${ACR_REGISTRY}/${ACR_NAMESPACE}/"
echo "  export VERSION=$VERSION"
echo "  docker-compose up -d"
echo "========================================"
