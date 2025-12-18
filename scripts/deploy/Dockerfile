# Unified Dockerfile for TqSDK Broker Connect
# This single image contains all 8 microservices
# docker-compose uses command overrides to start each service

FROM qpto_base_img:v0.1

# Set proxy for pip/uv access during build
ENV http_proxy=http://192.168.110.200:51081
ENV https_proxy=http://192.168.110.200:51081

RUN pip install --no-cache-dir uv

WORKDIR /workspaces/tqsdk_broker_connect

# Layer 1: Dependencies (cached unless pyproject.toml changes)
COPY --from=myapp pyproject.toml uv.lock README.md ./
RUN uv sync --frozen

# Layer 2: Shared utilities (common to all services)
COPY --from=myapp ./shared ./shared

# Layer 3: ALL 8 services in one layer
# This is efficient because each service is small
COPY --from=myapp ./services ./services

# Ensure proxy is cleared in final image
ENV http_proxy=""
ENV https_proxy=""

# Flexible entrypoint that allows command override in docker-compose
ENTRYPOINT ["/workspaces/tqsdk_broker_connect/.venv/bin/python"]

# Default command (will be overridden by docker-compose)
CMD ["/workspaces/tqsdk_broker_connect/services/tq_order_submitter/main.py"]
