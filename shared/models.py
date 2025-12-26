"""
Data models for TqSDK Broker Connect services
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any
import json


@dataclass
class OrderSubmitRequest:
    """External order submit request from qpto_engine"""
    symbol: str
    direction: str  # BUY or SELL
    offset: str     # OPEN, CLOSE, CLOSETODAY
    volume: int
    order_id: str
    portfolio_id: str
    limit_price: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderSubmitRequest':
        return cls(
            symbol=data['symbol'],
            direction=data['direction'],
            offset=data['offset'],
            volume=data['volume'],
            order_id=data['order_id'],
            portfolio_id=data['portfolio_id'],
            limit_price=data.get('limit_price')
        )


@dataclass
class OrderCancelRequest:
    """External order cancel request from qpto_engine"""
    order_id: str = ""
    cancel_type: str = "order_id"
    contract_code: str = ""
    portfolio_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderCancelRequest':
        return cls(
            order_id=data.get('order_id', ''),
            cancel_type=data.get('type', 'order_id'),
            contract_code=data.get('contract_code', ''),
            portfolio_id=data.get('portfolio_id', '')
        )


@dataclass
class FullPosition:
    """Full position data for Redis storage with all TqSDK position fields"""
    pos_long: int = 0
    pos_short: int = 0
    pos: int = 0  # net position = pos_long - pos_short
    pos_long_today: int = 0
    pos_long_his: int = 0
    pos_short_today: int = 0
    pos_short_his: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FullPosition':
        return cls(
            pos_long=int(data.get('pos_long', 0)),
            pos_short=int(data.get('pos_short', 0)),
            pos=int(data.get('pos', 0)),
            pos_long_today=int(data.get('pos_long_today', 0)),
            pos_long_his=int(data.get('pos_long_his', 0)),
            pos_short_today=int(data.get('pos_short_today', 0)),
            pos_short_his=int(data.get('pos_short_his', 0))
        )

    @classmethod
    def from_json(cls, json_str: str) -> 'FullPosition':
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_tqsdk_position(cls, pos) -> 'FullPosition':
        """Create from TqSDK position object"""
        return cls(
            pos_long=int(pos.pos_long),
            pos_short=int(pos.pos_short),
            pos=int(pos.pos_long - pos.pos_short),
            pos_long_today=int(pos.pos_long_today),
            pos_long_his=int(pos.pos_long_his),
            pos_short_today=int(pos.pos_short_today),
            pos_short_his=int(pos.pos_short_his)
        )

    @classmethod
    def zero(cls) -> 'FullPosition':
        """Create zero position"""
        return cls()

    def equals(self, other: 'FullPosition') -> bool:
        """Compare positions for equality (all fields)"""
        if other is None:
            return False
        return (self.pos_long == other.pos_long and
                self.pos_short == other.pos_short and
                self.pos == other.pos and
                self.pos_long_today == other.pos_long_today and
                self.pos_long_his == other.pos_long_his and
                self.pos_short_today == other.pos_short_today and
                self.pos_short_his == other.pos_short_his)


@dataclass
class PositionUpdate:
    """Position update message for internal queue"""
    type: str = "POSITION_UPDATE"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    portfolio_id: str = ""
    symbol: str = ""
    position: Optional[FullPosition] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'type': self.type,
            'timestamp': self.timestamp,
            'portfolio_id': self.portfolio_id,
            'symbol': self.symbol,
        }
        if self.position:
            result['position'] = self.position.to_dict()
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PositionUpdate':
        position = None
        if 'position' in data and data['position']:
            position = FullPosition.from_dict(data['position'])
        return cls(
            type=data.get('type', 'POSITION_UPDATE'),
            timestamp=data.get('timestamp', datetime.utcnow().isoformat()),
            portfolio_id=data.get('portfolio_id', ''),
            symbol=data.get('symbol', ''),
            position=position
        )


@dataclass
class TradeHistoryFuturesChn:
    """Trade record model - aligned with trade_history_futures_chn table"""
    trade_id: str = ""
    order_id: str = ""
    exchange_trade_id: str = ""
    exchange_id: str = ""
    instrument_id: str = ""
    direction: str = ""
    offset: str = ""
    price: float = 0.0
    volume: int = 0
    commission: float = 0.0
    trade_date_time: int = 0
    user_id: str = ""
    seqno: int = 0
    qpto_portfolio_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_tqsdk_trade(cls, trade_id: str, trade_data: Any, order_id: str, portfolio_id: str) -> 'TradeHistoryFuturesChn':
        """Create from TqSDK trade record"""
        return cls(
            trade_id=trade_id,
            order_id=order_id,
            exchange_trade_id=getattr(trade_data, 'exchange_trade_id', ''),
            exchange_id=getattr(trade_data, 'exchange_id', ''),
            instrument_id=getattr(trade_data, 'instrument_id', ''),
            direction=getattr(trade_data, 'direction', ''),
            offset=getattr(trade_data, 'offset', ''),
            price=float(getattr(trade_data, 'price', 0)),
            volume=int(getattr(trade_data, 'volume', 0)),
            commission=float(getattr(trade_data, 'commission', 0)),
            trade_date_time=int(getattr(trade_data, 'trade_date_time', 0)),
            user_id=getattr(trade_data, 'user_id', ''),
            seqno=int(getattr(trade_data, 'seqno', 0)),
            qpto_portfolio_id=portfolio_id
        )


@dataclass
class OrderHistoryFuturesChn:
    """Order model - aligned with order_history_futures_chn table"""
    # Primary key
    order_id: str = ""

    # TqSDK core fields
    exchange_order_id: str = ""
    exchange_id: str = ""
    instrument_id: str = ""
    direction: str = ""
    offset: str = ""
    volume_orign: int = 0
    volume_left: int = 0
    limit_price: float = 0.0
    price_type: str = ""
    volume_condition: str = ""
    time_condition: str = ""
    insert_date_time: int = 0
    last_msg: str = ""
    status: str = ""
    is_dead: bool = False
    is_online: bool = False
    is_error: bool = False
    trade_price: float = 0.0

    # QPTO Application fields
    qpto_portfolio_id: str = ""
    qpto_contract_code: str = ""
    sender_type: str = ""
    qpto_order_tag: str = ""
    qpto_trading_date: str = ""
    exchange_trading_date: str = ""
    origin_timestamp: int = 0

    # Trade records (for separate table processing)
    trade_records: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderHistoryFuturesChn':
        return cls(
            order_id=data.get('order_id', ''),
            exchange_order_id=data.get('exchange_order_id', ''),
            exchange_id=data.get('exchange_id', ''),
            instrument_id=data.get('instrument_id', ''),
            direction=data.get('direction', ''),
            offset=data.get('offset', ''),
            volume_orign=data.get('volume_orign', 0),
            volume_left=data.get('volume_left', 0),
            limit_price=data.get('limit_price', 0.0),
            price_type=data.get('price_type', ''),
            volume_condition=data.get('volume_condition', ''),
            time_condition=data.get('time_condition', ''),
            insert_date_time=data.get('insert_date_time', 0),
            last_msg=data.get('last_msg', ''),
            status=data.get('status', ''),
            is_dead=data.get('is_dead', False),
            is_online=data.get('is_online', False),
            is_error=data.get('is_error', False),
            trade_price=data.get('trade_price', 0.0),
            qpto_portfolio_id=data.get('qpto_portfolio_id', ''),
            qpto_contract_code=data.get('qpto_contract_code', ''),
            sender_type=data.get('sender_type', ''),
            qpto_order_tag=data.get('qpto_order_tag', ''),
            qpto_trading_date=data.get('qpto_trading_date', ''),
            exchange_trading_date=data.get('exchange_trading_date', ''),
            origin_timestamp=data.get('origin_timestamp', 0),
            trade_records=data.get('trade_records')
        )

    @classmethod
    def from_tqsdk_order(cls, order: Any, portfolio_id: str) -> 'OrderHistoryFuturesChn':
        """Create from TqSDK order object"""
        return cls(
            order_id=getattr(order, 'order_id', ''),
            exchange_order_id=getattr(order, 'exchange_order_id', ''),
            exchange_id=getattr(order, 'exchange_id', ''),
            instrument_id=getattr(order, 'instrument_id', ''),
            direction=getattr(order, 'direction', ''),
            offset=getattr(order, 'offset', ''),
            volume_orign=int(getattr(order, 'volume_orign', 0)),
            volume_left=int(getattr(order, 'volume_left', 0)),
            limit_price=float(getattr(order, 'limit_price', 0)),
            price_type=getattr(order, 'price_type', ''),
            volume_condition=getattr(order, 'volume_condition', ''),
            time_condition=getattr(order, 'time_condition', ''),
            insert_date_time=int(getattr(order, 'insert_date_time', 0)),
            last_msg=getattr(order, 'last_msg', ''),
            status=getattr(order, 'status', ''),
            is_dead=bool(getattr(order, 'is_dead', False)) if getattr(order, 'is_dead', None) is not None else False,
            is_online=bool(getattr(order, 'is_online', False)) if getattr(order, 'is_online', None) is not None else False,
            is_error=bool(getattr(order, 'is_error', False)) if getattr(order, 'is_error', None) is not None else False,
            trade_price=float(getattr(order, 'trade_price', 0)),
            qpto_portfolio_id=portfolio_id,
            trade_records=getattr(order, 'trade_records', None)
        )


@dataclass
class AccountUpdate:
    """Account update message for internal queue"""
    type: str = "ACCOUNT_UPDATE"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    portfolio_id: str = ""
    balance: float = 0
    available: float = 0
    margin: float = 0
    risk_ratio: float = 0
    position_profit: float = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AccountUpdate':
        return cls(
            type=data.get('type', 'ACCOUNT_UPDATE'),
            timestamp=data.get('timestamp', datetime.utcnow().isoformat()),
            portfolio_id=data.get('portfolio_id', ''),
            balance=data.get('balance', 0),
            available=data.get('available', 0),
            margin=data.get('margin', 0),
            risk_ratio=data.get('risk_ratio', 0),
            position_profit=data.get('position_profit', 0)
        )
