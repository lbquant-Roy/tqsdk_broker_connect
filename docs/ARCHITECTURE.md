# TqSDK Broker Connect - System Architecture

## Overview

TqSDK Broker Connect is a microservices-based system that connects the qpto_engine trading platform to China Futures markets via TqSDK.
The system uses an 8-container architecture to eliminate thread-safety issues and enable independent scaling of components.

## System Architecture Diagram

```
                              EXTERNAL (qpto_engine)
                                       │
           ┌───────────────────────────┴───────────────────────────┐
           │                                                       │
           ▼                                                       ▼
┌─────────────────────────┐                         ┌─────────────────────────┐
│   tq_order_submitter    │                         │   tq_order_canceller    │
│     (Container 1)       │                         │     (Container 2)       │
│     [Own TqApi]         │                         │     [Own TqApi]         │
│                         │                         │                         │
│ - Consumes SUBMIT       │                         │ - Consumes CANCEL       │
│   requests              │                         │   requests              │
│ - CLOSETODAY splitting  │                         │ - Calls api.cancel()    │
│ - Calls api.insert()    │                         │                         │
└─────────────────────────┘                         └─────────────────────────┘

┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│   tq_order_monitor      │  │  tq_position_monitor    │  │  tq_account_monitor     │
│     (Container 3)       │  │     (Container 4)       │  │     (Container 5)       │
│     [Own TqApi]         │  │     [Own TqApi]         │  │     [Own TqApi]         │
│                         │  │                         │  │                         │
│ - wait_update() loop    │  │ - wait_update() loop    │  │ - wait_update() loop    │
│ - Detects order changes │  │ - Detects position      │  │ - Detects account       │
│ - Publishes to MQ       │  │   changes               │  │   changes               │
│                         │  │ - Caches breakdown to   │  │ - Publishes to MQ       │
│                         │  │   Redis                 │  │                         │
│                         │  │ - Publishes to MQ       │  │                         │
└───────────┬─────────────┘  └───────────┬─────────────┘  └───────────┬─────────────┘
            │                            │                            │
            │    Internal RabbitMQ       │                            │
            ▼                            ▼                            ▼
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│   tq_order_handler      │  │  tq_position_handler    │  │  tq_account_handler     │
│     (Container 6)       │  │     (Container 7)       │  │     (Container 8)       │
│     [No TqApi]          │  │     [No TqApi]          │  │     [No TqApi]          │
│                         │  │                         │  │                         │
│ - Consumes order        │  │ - Consumes position     │  │ - Consumes account      │
│   updates from MQ       │  │   updates from MQ       │  │   updates from MQ       │
│ - Writes to PostgreSQL  │  │ - Writes to Redis       │  │ - Writes to Redis       │
│   (order_history,       │  │   with TTL              │  │   with TTL              │
│    order_event)         │  │                         │  │                         │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
```

## Container Responsibilities

### Container 1: tq_order_submitter
- **Purpose**: Execute order submissions
- **TqApi**: Own instance
- **Input**: External RabbitMQ queue `tq_order_submit_requests`
- **Operations**:
  - Validates order requests
  - Handles CLOSETODAY splitting for SHFE/INE exchanges
  - Reads position breakdown from Redis for splitting
  - Calls `api.insert_order()` to submit orders

### Container 2: tq_order_canceller
- **Purpose**: Execute order cancellations
- **TqApi**: Own instance
- **Input**: External RabbitMQ queue `tq_order_cancel_requests`
- **Operations**:
  - Validates cancel requests
  - Calls `api.cancel_order()` to cancel orders

### Container 3: tq_order_monitor
- **Purpose**: Monitor order status changes
- **TqApi**: Own instance
- **Output**: Internal RabbitMQ queue `tq_internal_order_updates`
- **Operations**:
  - Runs continuous `wait_update()` loop
  - Detects order status transitions (ALIVE → FINISHED)
  - Detects volume_left changes (partial fills)
  - Publishes order update events to internal queue

### Container 4: tq_position_monitor
- **Purpose**: Monitor position changes
- **TqApi**: Own instance
- **Output**: Internal RabbitMQ queue `tq_internal_position_updates`
- **Operations**:
  - Runs continuous `wait_update()` loop
  - Calculates net position (pos_long - pos_short)
  - Caches position breakdown to Redis for CLOSETODAY splitting
  - Publishes position updates to internal queue

### Container 5: tq_account_monitor
- **Purpose**: Monitor account balance changes
- **TqApi**: Own instance
- **Output**: Internal RabbitMQ queue `tq_internal_account_updates`
- **Operations**:
  - Runs continuous `wait_update()` loop
  - Monitors account balance, margin, risk ratio
  - Publishes account updates to internal queue

### Container 6: tq_order_handler
- **Purpose**: Persist order data to database
- **TqApi**: None (pure data handler)
- **Input**: Internal RabbitMQ queue `tq_internal_order_updates`
- **Output**: PostgreSQL tables
- **Operations**:
  - Consumes order updates from internal queue
  - Writes to `order_history` table (upsert)
  - Writes to `order_event` table (insert)

### Container 7: tq_position_handler
- **Purpose**: Persist position data to Redis
- **TqApi**: None (pure data handler)
- **Input**: Internal RabbitMQ queue `tq_internal_position_updates`
- **Output**: Redis
- **Operations**:
  - Consumes position updates from internal queue
  - Writes net position to Redis with TTL

### Container 8: tq_account_handler
- **Purpose**: Persist account data to Redis
- **TqApi**: None (pure data handler)
- **Input**: Internal RabbitMQ queue `tq_internal_account_updates`
- **Output**: Redis
- **Operations**:
  - Consumes account updates from internal queue
  - Writes account info to Redis with TTL

## Message Queue Design

### External Queues (from qpto_engine)

| Queue | Exchange | Consumer | Purpose |
|-------|----------|----------|---------|
| `tq_order_submit_requests` | `tq_order_request_exchange` | tq_order_submitter | Submit new orders |
| `tq_order_cancel_requests` | `tq_order_request_exchange` | tq_order_canceller | Cancel existing orders |

### Internal Queues (between containers)

| Queue | Exchange | Producer | Consumer | Purpose |
|-------|----------|----------|----------|---------|
| `tq_internal_order_updates` | `tq_internal_exchange` | tq_order_monitor | tq_order_handler | Order status updates |
| `tq_internal_position_updates` | `tq_internal_exchange` | tq_position_monitor | tq_position_handler | Position changes |
| `tq_internal_account_updates` | `tq_internal_exchange` | tq_account_monitor | tq_account_handler | Account balance updates |

## API Reference

### Order Submit Request

**Queue**: `tq_order_submit_requests`

```json
{
  "type": "SUBMIT",
  "request_id": "uuid-string",
  "timestamp": "2025-12-18T10:30:00Z",
  "payload": {
    "symbol": "SHFE.rb2505",
    "direction": "BUY",
    "offset": "OPEN",
    "volume": 10,
    "limit_price": 3500.0,
    "order_id": "unique-order-id",
    "portfolio_id": "1234567890"
  }
}
```

**Fields**:
- `type`: Always "SUBMIT" for order submission
- `request_id`: Unique identifier for this request
- `timestamp`: ISO8601 timestamp
- `payload.symbol`: TqSDK symbol format (EXCHANGE.contract)
- `payload.direction`: "BUY" or "SELL"
- `payload.offset`: "OPEN", "CLOSE", or "CLOSETODAY"
- `payload.volume`: Number of contracts
- `payload.limit_price`: Limit price (optional, omit for market order)
- `payload.order_id`: Your order tracking ID
- `payload.portfolio_id`: Portfolio identifier

### Order Cancel Request

**Queue**: `tq_order_cancel_requests`

```json
{
  "type": "CANCEL",
  "request_id": "uuid-string",
  "timestamp": "2025-12-18T10:31:00Z",
  "payload": {
    "order_id": "unique-order-id",
    "portfolio_id": "1234567890"
  }
}
```

### Internal Order Update

**Queue**: `tq_internal_order_updates`

```json
{
  "type": "ORDER_UPDATE",
  "timestamp": "2025-12-18T10:30:05Z",
  "portfolio_id": "1234567890",
  "order_id": "unique-order-id",
  "exchange_order_id": "exchange-assigned-id",
  "symbol": "SHFE.rb2505",
  "direction": "BUY",
  "offset": "OPEN",
  "status": "FINISHED",
  "event_type": "COMPLETE_FILL",
  "volume_orign": 10,
  "volume_left": 0,
  "filled_quantity": 10,
  "limit_price": 3500.0,
  "trade_price": 3498.5,
  "insert_date_time": 1734521405000000000
}
```

**Event Types**:
- `COMPLETE_FILL`: Order fully filled (volume_left = 0)
- `PARTIAL_FILL`: Order partially filled (volume_left decreased)
- `CANCELLED`: Order cancelled
- `REJECTED`: Order rejected by exchange

### Internal Position Update

**Queue**: `tq_internal_position_updates`

```json
{
  "type": "POSITION_UPDATE",
  "timestamp": "2025-12-18T10:30:05Z",
  "portfolio_id": "1234567890",
  "symbol": "SHFE.rb2505",
  "net_position": 10,
  "breakdown": {
    "pos_long": 10,
    "pos_short": 0,
    "pos_long_today": 5,
    "pos_long_his": 5,
    "pos_short_today": 0,
    "pos_short_his": 0
  }
}
```

### Internal Account Update

**Queue**: `tq_internal_account_updates`

```json
{
  "type": "ACCOUNT_UPDATE",
  "timestamp": "2025-12-18T10:30:05Z",
  "portfolio_id": "1234567890",
  "balance": 1000000.0,
  "available": 800000.0,
  "margin": 150000.0,
  "float_profit": 5000.0,
  "position_profit": 3000.0,
  "risk_ratio": 0.15
}
```

## Redis Key Patterns

| Key Pattern | Description | TTL |
|-------------|-------------|-----|
| `TQ_Position_PortfolioId_{id}_Symbol_{symbol}` | Net position value | 1 hour |
| `TQ_Position_Breakdown_PortfolioId_{id}_Symbol_{symbol}` | Position breakdown JSON | 1 hour |
| `TQ_Account_PortfolioId_{id}` | Account info JSON | 1 hour |

## PostgreSQL Schema

### order_history

```sql
CREATE TABLE order_history (
    id VARCHAR PRIMARY KEY,           -- order_id
    exchange_order_id VARCHAR,
    portfolio_id VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    direction VARCHAR NOT NULL,
    offset VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    volume_orign INTEGER,
    volume_left INTEGER,
    filled_quantity INTEGER,
    limit_price DECIMAL,
    trade_price DECIMAL,
    insert_date_time BIGINT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### order_event

```sql
CREATE TABLE order_event (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR NOT NULL,
    portfolio_id VARCHAR NOT NULL,
    status VARCHAR NOT NULL,          -- event_type
    msg JSONB,                        -- full order data
    created_at TIMESTAMP DEFAULT NOW()
);
```

## CLOSETODAY Handling

SHFE (Shanghai Futures Exchange) and INE (International Energy Exchange) require separate handling for positions opened today vs historical positions:

1. **Position Monitor** caches breakdown to Redis:
   - Key: `TQ_Position_Breakdown_PortfolioId_{id}_Symbol_{symbol}`
   - Value: `{"pos_long_today": 5, "pos_long_his": 10, ...}`

2. **Order Submitter** reads breakdown and splits CLOSE orders:
   - CLOSETODAY order for today's positions (suffix: `_closetoday`)
   - CLOSE order for historical positions (suffix: `_close`)

## Deployment

### Docker Images

| Image Name | Version | Source |
|------------|---------|--------|
| tq_order_submitter | v0.2.0 | Dockerfile.order_submitter |
| tq_order_canceller | v0.2.0 | Dockerfile.order_canceller |
| tq_order_monitor | v0.2.0 | Dockerfile.order_monitor |
| tq_position_monitor | v0.2.0 | Dockerfile.position_monitor |
| tq_account_monitor | v0.2.0 | Dockerfile.account_monitor |
| tq_order_handler | v0.2.0 | Dockerfile.order_handler |
| tq_position_handler | v0.2.0 | Dockerfile.position_handler |
| tq_account_handler | v0.2.0 | Dockerfile.account_handler |

### Build Commands

```bash
cd scripts/deploy

# Build all images
./build_all_images.sh -e local

# Build and sync to Aliyun
./build_all_images.sh -e aliyun
```

### Docker Compose

```bash
cd scripts/deploy/tqsdk_broker_connect

# Set environment variables
export CONFIG_PATH=/path/to/config.yaml
export LOG_PATH=/path/to/logs

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

## Configuration

Configuration is loaded from `config.yaml`:

```yaml
tq:
  username: "your_username"
  password: "your_password"
  portfolio_id: "your_portfolio_id"
  run_mode: "sandbox"  # Options: real, sandbox

redis:
  host: "192.168.110.200"
  port: 6379
  password: "your_password"
  db: 1

rabbitmq:
  url: "amqp://user:pass@host:5672/vhost"
  external:
    order_submit_queue: "tq_order_submit_requests"
    order_cancel_queue: "tq_order_cancel_requests"
    order_exchange: "tq_order_request_exchange"
  internal:
    exchange: "tq_internal_exchange"
    order_updates_queue: "tq_internal_order_updates"
    position_updates_queue: "tq_internal_position_updates"
    account_updates_queue: "tq_internal_account_updates"

database:
  host: "192.168.110.200"
  port: 5432
  user: "postgres"
  password: "your_password"
  dbname: "qpto_futures_chn"
```

## Network Requirements

All containers run with `network_mode: "host"` to connect to existing infrastructure:
- Redis: 192.168.110.200:6379
- RabbitMQ: 192.168.110.200:5672
- PostgreSQL: 192.168.110.200:5432
- TqSDK servers (internet access required)

## Graceful Shutdown

All services handle SIGINT/SIGTERM for graceful shutdown:
1. Stop consuming new messages
2. Complete in-flight operations
3. Close TqApi connection (if applicable)
4. Close database/Redis connections
5. Exit cleanly

## Logging

All services use Loguru with:
- Console output: INFO level with colors
- File output: `logs/` directory with rotation (10MB, 7 days retention)
- Log format includes timestamp, level, module, and message
