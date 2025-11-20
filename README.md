# TqSDK Broker Connect

Separate TqAPI connection service that communicates with `qpto_engine` via RabbitMQ. This project decouples the TqSDK connection from the main trading engine, enabling independent deployment and better scalability.

## Architecture

```
qpto_engine → RabbitMQ (order requests) → tqsdk_broker_connect → TqApi
qpto_engine ← Redis (positions)        ← tqsdk_broker_connect ← TqApi
qpto_engine ← PostgreSQL (orders)      ← tqsdk_broker_connect ← TqApi
```

## Features

- **Separate Deployment**: Run TqSDK connection independently from qpto_engine
- **RabbitMQ Integration**: Async order execution via message queue
- **Position Tracking**: Real-time position updates stored in Redis
- **Order Management**: Order status updates stored in PostgreSQL
- **Account Monitoring**: Continuous monitoring of account data and positions
- **Graceful Shutdown**: Proper cleanup of connections and resources

## Project Structure

```
tqsdk_broker_connect/
├── config.yaml                    # Configuration file
├── requirements.txt               # Python dependencies
├── main.py                        # Main entry point
├── tqsdk_client/
│   ├── __init__.py
│   ├── config.py                  # Configuration management
│   ├── tq_data_stream.py          # TQ account data stream handler
│   ├── order_executor.py          # Order request executor
│   └── data_processor.py          # Data processing and storage
└── README.md
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure `config.yaml`:
```yaml
tq:
  username: "your_tq_username"
  password: "your_tq_password"
  portfolio_id: "your_portfolio_id"
  run_mode: "sandbox"  # Options: real, sandbox

redis:
  host: "172.31.15.55"
  port: 6379
  password: "your_password"
  db: 1

rabbitmq:
  url: "amqp://guest:guest@localhost:5672/"
  order_request_queue: "tq_order_requests"
  order_request_exchange: "tq_ws_api_request_exchange"
  order_request_routing_key: "PortfolioId_{portfolio_id}"

database:
  host: "localhost"
  port: 5555
  user: "postgres"
  password: "postgres"
  dbname: "postgres"
```

## Usage

### Start the Service

```bash
python main.py
```

The service will:
1. Connect to TqApi using configured credentials
2. Start monitoring account positions and orders
3. Listen for order requests on RabbitMQ
4. Update positions to Redis and orders to PostgreSQL

### Order Request Format

Send order requests to RabbitMQ queue `tq_order_requests`:

```json
{
  "symbol": "SHFE.rb2505",
  "direction": "BUY",
  "offset": "OPEN",
  "volume": 1,
  "limit_price": 3500.0,
  "order_id": "unique-order-id",
  "portfolio_id": "your_portfolio_id"
}
```

### Position Data in Redis

Positions are stored with TTL (1 hour) in Redis:

**Key format**: `TQ_Position_PortfolioId_{portfolio_id}_Symbol_{symbol}`

**Value**: Position amount (positive for long, negative for short)

### Order Data in PostgreSQL

Order updates are stored in two tables:
- `order_history`: Order details and current status
- `order_event`: Event log of all order status changes

## Components

### TqDataStreamHandler
- Connects to TqApi and maintains the connection
- Monitors position changes via `wait_update()`
- Monitors order status changes
- Publishes updates to DataProcessor

### OrderExecutor
- Consumes order requests from RabbitMQ
- Executes orders via TqApi
- Handles order cancellations
- Auto-reconnects to RabbitMQ on disconnect

### DataProcessor
- Stores position updates in Redis
- Stores order updates in PostgreSQL
- Stores account information in Redis
- Provides data access methods

## Integration with qpto_engine

To integrate with qpto_engine, modify `futures_chn_broker_tq.py`:

1. Remove direct TqApi instantiation
2. Publish orders to RabbitMQ instead of calling `api.insert_order()`
3. Read positions from Redis instead of `api.get_position()`
4. Query order status from PostgreSQL instead of `api.get_order()`

## Monitoring

Logs are written to:
- Console (stdout)
- File: `tqsdk_broker_connect.log`

Log levels:
- INFO: Normal operations
- WARNING: Recoverable issues
- ERROR: Problems requiring attention

## Shutdown

Press `Ctrl+C` or send `SIGTERM` for graceful shutdown:
1. Stop order executor
2. Stop data stream handler
3. Close TqApi connection
4. Close Redis and PostgreSQL connections

## Troubleshooting

### Connection Issues
- Check TQ credentials in config.yaml
- Verify Redis/RabbitMQ/PostgreSQL connectivity
- Check firewall rules

### Order Not Executing
- Verify RabbitMQ queue configuration
- Check order request format
- Review logs for error messages

### Position Not Updating
- Ensure TqApi connection is active
- Check Redis connection
- Verify symbol format matches TqSDK format

## Similar Projects

This project follows the same architecture as `binance_broker_connect`, which handles Binance Futures broker connections separately from the main engine.

## License

Internal project - not for public distribution
