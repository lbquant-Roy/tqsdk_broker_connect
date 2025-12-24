"""
TqApi factory for creating TqApi instances
"""
from loguru import logger
from tqsdk import TqApi, TqAuth, TqKq
from .config import Config


def create_tqapi(config: Config) -> TqApi:
    """
    Create a new TqApi instance

    Each container should have its own TqApi instance for thread safety.
    """
    auth = TqAuth(config.tq_username, config.tq_password)
    account = TqKq()

    logger.info(f"Creating TqApi instance for portfolio {config.portfolio_id}")
    api = TqApi(account=account, auth=auth)

    _ = api.get_quote("KQ.m@SHFE.au")
    _ = api.get_account()
    _ = api.get_order()

    logger.info("TqApi instance created successfully")
    return api


def close_tqapi(api: TqApi):
    """Close TqApi instance gracefully"""
    if api:
        try:
            api.close()
            logger.info("TqApi instance closed")
        except Exception as e:
            logger.error(f"Error closing TqApi: {e}")
