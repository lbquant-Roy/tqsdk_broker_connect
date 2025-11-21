"""
Configuration management for TqSDK Broker Connect
"""
import os
import yaml
from typing import Dict, Any
from loguru import logger


class Config:
    """Configuration manager for TqSDK broker connect"""

    def __init__(self, config_path: str = None):
        """
        Initialize configuration

        Parameters
        ----------
        config_path : str, optional
            Path to config.yaml file
        """
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'config.yaml'
            )

        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    @property
    def tq(self) -> Dict[str, Any]:
        """Get TQ configuration"""
        return self.config.get('tq', {})

    @property
    def redis(self) -> Dict[str, Any]:
        """Get Redis configuration"""
        return self.config.get('redis', {})

    @property
    def rabbitmq(self) -> Dict[str, Any]:
        """Get RabbitMQ configuration"""
        return self.config.get('rabbitmq', {})

    @property
    def database(self) -> Dict[str, Any]:
        """Get database configuration"""
        return self.config.get('database', {})

    @property
    def portfolio_id(self) -> str:
        """Get portfolio ID"""
        return self.tq.get('portfolio_id', '')

    @property
    def run_mode(self) -> str:
        """Get run mode (real/sandbox)"""
        return self.tq.get('run_mode', 'sandbox')

    def get_redis_position_key(self, symbol: str) -> str:
        """
        Get Redis key for position storage

        Parameters
        ----------
        symbol : str
            Trading symbol

        Returns
        -------
        str
            Redis key for position
        """
        return f"TQ_Position_PortfolioId_{self.portfolio_id}_Symbol_{symbol}"

    def get_rabbitmq_routing_key(self) -> str:
        """
        Get RabbitMQ routing key for this portfolio

        Returns
        -------
        str
            RabbitMQ routing key
        """
        template = self.rabbitmq.get('order_request_routing_key', 'PortfolioId_{portfolio_id}')
        return template.format(portfolio_id=self.portfolio_id)


# Singleton instance
_config_instance = None


def get_config(config_path: str = None) -> Config:
    """
    Get configuration singleton instance

    Parameters
    ----------
    config_path : str, optional
        Path to config file

    Returns
    -------
    Config
        Configuration instance
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = Config(config_path)

    return _config_instance
