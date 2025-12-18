"""
Configuration management for TqSDK Broker Connect services
"""
import os
import yaml
from typing import Dict, Any
from loguru import logger


class Config:
    """Configuration manager for TqSDK broker connect services"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            # Try multiple locations
            possible_paths = [
                os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml'),
                '/workspace/tqsdk_broker_connect/config.yaml',
                'config.yaml'
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break
            else:
                config_path = possible_paths[0]

        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
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
        return self.config.get('tq', {})

    @property
    def redis(self) -> Dict[str, Any]:
        return self.config.get('redis', {})

    @property
    def rabbitmq(self) -> Dict[str, Any]:
        return self.config.get('rabbitmq', {})

    @property
    def database(self) -> Dict[str, Any]:
        return self.config.get('database', {})

    @property
    def portfolio_id(self) -> str:
        return self.tq.get('portfolio_id', '')

    @property
    def run_mode(self) -> str:
        return self.tq.get('run_mode', 'sandbox')

    @property
    def tq_username(self) -> str:
        return self.tq.get('username', '')

    @property
    def tq_password(self) -> str:
        return self.tq.get('password', '')


# Singleton instance
_config_instance = None


def get_config(config_path: str = None) -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path)
    return _config_instance
