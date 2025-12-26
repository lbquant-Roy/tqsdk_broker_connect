"""
Constants for TqSDK Broker Connect services
"""

# External RabbitMQ Queues (from qpto_engine)
EXTERNAL_ORDER_SUBMIT_QUEUE = "tq_order_submit_requests"
EXTERNAL_ORDER_CANCEL_QUEUE = "tq_order_cancel_requests"
EXTERNAL_ORDER_EXCHANGE = "tq_order_request_exchange"

# Internal RabbitMQ Queues (between containers)
INTERNAL_EXCHANGE = "tq_internal_exchange"
INTERNAL_ORDER_UPDATES_QUEUE = "tq_internal_order_updates"
INTERNAL_ACCOUNT_UPDATES_QUEUE = "tq_internal_account_updates"

# Routing Keys
ROUTING_KEY_ORDER_UPDATES = "order_updates"
ROUTING_KEY_ACCOUNT_UPDATES = "account_updates"

# Redis Key Patterns
REDIS_POSITION_KEY_PATTERN = "TQ_Position_PortfolioId_{portfolio_id}_Symbol_{symbol}"
REDIS_ACCOUNT_KEY_PATTERN = "TQ_Account_PortfolioId_{portfolio_id}"

# TTL in seconds
POSITION_TTL = 15    # 15 seconds (short TTL for real-time tracking)
ACCOUNT_TTL = 3600   # 1 hour

# Order expiration
ORDER_EXPIRE_ALLOW_MAX = 5  # Maximum allowed age for order in seconds

# Position monitor intervals
POSITION_LOOP_INTERVAL_SECONDS = 5    # Loop monitor check interval
UNIVERSE_REFRESH_INTERVAL_SECONDS = 1800  # 30 minutes for universe refresh

# Exchanges that require CLOSETODAY handling
CLOSETODAY_EXCHANGES = {"SHFE", "INE"}
