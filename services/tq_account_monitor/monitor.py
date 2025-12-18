"""
Account monitoring logic using TqApi wait_update()
"""
from typing import Dict, Any, Callable, Optional
from loguru import logger
from tqsdk import TqApi


class AccountMonitor:
    """Monitor account changes from TqApi"""

    def __init__(self, api: TqApi, portfolio_id: str):
        self.api = api
        self.portfolio_id = portfolio_id
        self.previous_account: Optional[Dict[str, Any]] = None
        self.running = False

    def start(self, on_update: Callable[[Dict[str, Any]], None]):
        """Start monitoring account changes"""
        self.running = True
        logger.info("Account monitor started")

        while self.running:
            try:
                self.api.wait_update()
                self._check_account_updates(on_update)
            except Exception as e:
                if self.running:
                    logger.error(f"Error in account monitor loop: {e}")

    def stop(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Account monitor stopping...")

    def _check_account_updates(self, on_update: Callable[[Dict[str, Any]], None]):
        """Check for account changes and publish updates"""
        account = self.api.get_account()

        current_account = {
            'balance': account.balance,
            'available': account.available,
            'margin': account.margin,
            'risk_ratio': account.risk_ratio if hasattr(account, 'risk_ratio') else 0,
            'position_profit': account.position_profit if hasattr(account, 'position_profit') else 0
        }

        # Check if account changed
        if self.previous_account is None or self._account_changed(current_account):
            update = {
                'type': 'ACCOUNT_UPDATE',
                'portfolio_id': self.portfolio_id,
                **current_account
            }

            logger.info(f"Account update: balance={current_account['balance']:.2f}")
            on_update(update)

        self.previous_account = current_account

    def _account_changed(self, current: Dict[str, Any]) -> bool:
        """Check if account state changed significantly"""
        if self.previous_account is None:
            return True

        # Check for significant changes (threshold 0.01 to avoid float noise)
        for key in ['balance', 'available', 'margin', 'position_profit']:
            prev_val = self.previous_account.get(key, 0)
            curr_val = current.get(key, 0)
            if abs(prev_val - curr_val) > 0.01:
                return True

        return False
