-- Migration: Create order_history_futures_chn and trade_history_futures_chn tables
-- Description: Refactor order_history table to align with tqsdk.objs.Order schema
-- Date: 2025-12-26

-- Drop old table (no data migration)
DROP TABLE IF EXISTS order_history;

-- Create new order history table
CREATE TABLE order_history_futures_chn (
    -- Primary key
    order_id VARCHAR(255) PRIMARY KEY,

    -- TqSDK core fields
    exchange_order_id VARCHAR(255) DEFAULT '',
    exchange_id VARCHAR(50) DEFAULT '',            -- SHFE, DCE, CZCE, INE
    instrument_id VARCHAR(50) NOT NULL,            -- Contract code (e.g., ru2605)
    direction VARCHAR(10) NOT NULL,                -- BUY, SELL
    offset VARCHAR(20) NOT NULL,                   -- OPEN, CLOSE, CLOSETODAY
    volume_orign INTEGER NOT NULL,                 -- Total order volume
    volume_left INTEGER DEFAULT 0,                 -- Unfilled volume
    limit_price DECIMAL(20, 8) DEFAULT 0,          -- Limit price
    price_type VARCHAR(20) DEFAULT '',             -- ANY (market), LIMIT
    volume_condition VARCHAR(20) DEFAULT '',       -- ANY, MIN, ALL
    time_condition VARCHAR(20) DEFAULT '',         -- IOC, GFS, GFD, GTC, GFA
    insert_date_time BIGINT DEFAULT 0,             -- Order submission time (nanoseconds)
    last_msg TEXT DEFAULT '',                      -- Status message
    status VARCHAR(20) DEFAULT '',                 -- ALIVE, FINISHED
    is_dead BOOLEAN DEFAULT FALSE,                 -- Order cannot produce more fills
    is_online BOOLEAN DEFAULT FALSE,               -- Order confirmed at exchange
    is_error BOOLEAN DEFAULT FALSE,                -- Order failed
    trade_price DECIMAL(20, 8) DEFAULT 0,          -- Average fill price

    -- QPTO Application fields
    qpto_portfolio_id VARCHAR(255) NOT NULL,       -- Required for filtering
    qpto_contract_code VARCHAR(50) DEFAULT '',     -- Input symbol (same as symbol from message)
    sender_type VARCHAR(100) DEFAULT '',           -- Service name (e.g., tq_submitter)
    qpto_order_tag VARCHAR(100) DEFAULT '',        -- Order tag
    qpto_trading_date VARCHAR(10) DEFAULT '',      -- Trading date (format: YYYY-MM-DD)
    exchange_trading_date VARCHAR(10) DEFAULT '',  -- Exchange trading date (format: YYYY-MM-DD)
    origin_timestamp BIGINT DEFAULT 0,             -- Timestamp from message (nanoseconds)

    -- System timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_order_history_futures_chn_qpto_portfolio_id
    ON order_history_futures_chn(qpto_portfolio_id);
CREATE INDEX idx_order_history_futures_chn_instrument_id
    ON order_history_futures_chn(instrument_id);
CREATE INDEX idx_order_history_futures_chn_status
    ON order_history_futures_chn(status);
CREATE INDEX idx_order_history_futures_chn_created_at
    ON order_history_futures_chn(created_at);
CREATE INDEX idx_order_history_futures_chn_portfolio_instrument
    ON order_history_futures_chn(qpto_portfolio_id, instrument_id);
CREATE INDEX idx_order_history_futures_chn_status_created
    ON order_history_futures_chn(status, created_at);
CREATE INDEX idx_order_history_futures_chn_qpto_contract_code
    ON order_history_futures_chn(qpto_contract_code);

-- Create trade history table
CREATE TABLE trade_history_futures_chn (
    -- Primary key
    trade_id VARCHAR(255) PRIMARY KEY,

    -- Reference to order
    order_id VARCHAR(255) NOT NULL,

    -- TqSDK trade record fields
    exchange_trade_id VARCHAR(255) DEFAULT '',
    exchange_id VARCHAR(50) DEFAULT '',
    instrument_id VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,         -- BUY, SELL
    offset VARCHAR(20) NOT NULL,            -- OPEN, CLOSE, CLOSETODAY
    price DECIMAL(20, 8) NOT NULL,          -- Fill price
    volume INTEGER NOT NULL,                -- Fill volume
    commission DECIMAL(20, 8) DEFAULT 0,    -- Commission for this trade
    trade_date_time BIGINT DEFAULT 0,       -- Trade execution time (nanoseconds)
    user_id VARCHAR(255) DEFAULT '',
    seqno INTEGER DEFAULT 0,

    -- Application fields
    qpto_portfolio_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for trade history
CREATE INDEX idx_trade_history_futures_chn_order_id
    ON trade_history_futures_chn(order_id);
CREATE INDEX idx_trade_history_futures_chn_qpto_portfolio_id
    ON trade_history_futures_chn(qpto_portfolio_id);
CREATE INDEX idx_trade_history_futures_chn_instrument_id
    ON trade_history_futures_chn(instrument_id);
CREATE INDEX idx_trade_history_futures_chn_trade_date_time
    ON trade_history_futures_chn(trade_date_time);
