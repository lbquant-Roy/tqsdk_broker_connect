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
class PositionBreakdown:
    """Position breakdown for CLOSETODAY handling"""
    pos_long_today: int = 0
    pos_long_his: int = 0
    pos_short_today: int = 0
    pos_short_his: int = 0
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PositionBreakdown':
        return cls(
            pos_long_today=data.get('pos_long_today', 0),
            pos_long_his=data.get('pos_long_his', 0),
            pos_short_today=data.get('pos_short_today', 0),
            pos_short_his=data.get('pos_short_his', 0),
            updated_at=data.get('updated_at', datetime.utcnow().isoformat())
        )

    @classmethod
    def from_json(cls, json_str: str) -> 'PositionBreakdown':
        return cls.from_dict(json.loads(json_str))


@dataclass
class PositionUpdate:
    """Position update message for internal queue"""
    type: str = "POSITION_UPDATE"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    portfolio_id: str = ""
    symbol: str = ""
    net_position: float = 0
    breakdown: Optional[PositionBreakdown] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'type': self.type,
            'timestamp': self.timestamp,
            'portfolio_id': self.portfolio_id,
            'symbol': self.symbol,
            'net_position': self.net_position,
        }
        if self.breakdown:
            result['breakdown'] = self.breakdown.to_dict()
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PositionUpdate':
        breakdown = None
        if 'breakdown' in data and data['breakdown']:
            breakdown = PositionBreakdown.from_dict(data['breakdown'])
        return cls(
            type=data.get('type', 'POSITION_UPDATE'),
            timestamp=data.get('timestamp', datetime.utcnow().isoformat()),
            portfolio_id=data.get('portfolio_id', ''),
            symbol=data.get('symbol', ''),
            net_position=data.get('net_position', 0),
            breakdown=breakdown
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
