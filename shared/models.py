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
    order_id: str
    portfolio_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderCancelRequest':
        return cls(
            order_id=data['order_id'],
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
class OrderUpdate:
    """Order update message for internal queue"""
    type: str = "ORDER_UPDATE"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    portfolio_id: str = ""
    order_id: str = ""
    status: str = ""
    event_type: str = ""
    filled_quantity: float = 0
    symbol: str = ""
    direction: str = ""
    offset: str = ""
    volume_orign: int = 0
    volume_left: int = 0
    limit_price: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderUpdate':
        return cls(
            type=data.get('type', 'ORDER_UPDATE'),
            timestamp=data.get('timestamp', datetime.utcnow().isoformat()),
            portfolio_id=data.get('portfolio_id', ''),
            order_id=data.get('order_id', ''),
            status=data.get('status', ''),
            event_type=data.get('event_type', ''),
            filled_quantity=data.get('filled_quantity', 0),
            symbol=data.get('symbol', ''),
            direction=data.get('direction', ''),
            offset=data.get('offset', ''),
            volume_orign=data.get('volume_orign', 0),
            volume_left=data.get('volume_left', 0),
            limit_price=data.get('limit_price')
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
