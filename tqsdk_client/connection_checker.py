"""
Connection checker for validating external service availability
"""
import redis
import pika
from sqlalchemy import create_engine, text
from tqsdk import TqApi, TqAuth, TqKq
from typing import Tuple
from loguru import logger

from .config import Config


def check_redis_connection(config: Config, timeout: int = 5) -> Tuple[bool, str]:
    """
    Check Redis connection

    Parameters
    ----------
    config : Config
        Configuration instance
    timeout : int
        Connection timeout in seconds

    Returns
    -------
    tuple
        (success: bool, error_msg: str)
    """
    try:
        redis_config = config.redis
        client = redis.Redis(
            host=redis_config['host'],
            port=redis_config['port'],
            password=redis_config['password'],
            db=redis_config['db'],
            decode_responses=True,
            socket_connect_timeout=timeout,
            socket_timeout=timeout
        )

        # Test connection with ping
        client.ping()
        client.close()

        logger.info(f"✓ Redis connection OK ({redis_config['host']}:{redis_config['port']})")
        return True, ""

    except redis.ConnectionError as e:
        error_msg = f"Redis connection failed: {e}"
        logger.error(error_msg)
        return False, error_msg
    except redis.TimeoutError as e:
        error_msg = f"Redis connection timeout: {e}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Redis connection error: {e}"
        logger.error(error_msg)
        return False, error_msg


def check_postgres_connection(config: Config, timeout: int = 5) -> Tuple[bool, str]:
    """
    Check PostgreSQL connection

    Parameters
    ----------
    config : Config
        Configuration instance
    timeout : int
        Connection timeout in seconds

    Returns
    -------
    tuple
        (success: bool, error_msg: str)
    """
    try:
        db_config = config.database
        db_url = (
            f"postgresql://{db_config['user']}:{db_config['password']}"
            f"@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
            f"?connect_timeout={timeout}"
        )

        # Create engine and test connection
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

        engine.dispose()

        logger.info(f"✓ PostgreSQL connection OK ({db_config['host']}:{db_config['port']})")
        return True, ""

    except Exception as e:
        error_msg = f"PostgreSQL connection failed: {e}"
        logger.error(error_msg)
        return False, error_msg


def check_rabbitmq_connection(config: Config, timeout: int = 5) -> Tuple[bool, str]:
    """
    Check RabbitMQ connection

    Parameters
    ----------
    config : Config
        Configuration instance
    timeout : int
        Connection timeout in seconds

    Returns
    -------
    tuple
        (success: bool, error_msg: str)
    """
    try:
        rabbitmq_config = config.rabbitmq

        # Create connection with timeout
        parameters = pika.URLParameters(rabbitmq_config['url'])
        parameters.connection_attempts = 1
        parameters.socket_timeout = timeout

        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        # Test by declaring exchange (idempotent operation)
        exchange_name = rabbitmq_config['order_request_exchange']
        channel.exchange_declare(
            exchange=exchange_name,
            exchange_type='topic',
            durable=True,
            passive=True  # Check if exists without creating
        )

        connection.close()

        logger.info(f"✓ RabbitMQ connection OK")
        return True, ""

    except pika.exceptions.ChannelClosedByBroker:
        # Exchange doesn't exist yet, but connection works
        logger.info(f"✓ RabbitMQ connection OK (exchange will be created)")
        return True, ""
    except pika.exceptions.AMQPConnectionError as e:
        error_msg = f"RabbitMQ connection failed: {e}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"RabbitMQ connection error: {e}"
        logger.error(error_msg)
        return False, error_msg


def check_tqsdk_connection(config: Config, timeout: int = 5) -> Tuple[bool, str]:
    """
    Check TqSDK API connection

    Parameters
    ----------
    config : Config
        Configuration instance
    timeout : int
        Connection timeout in seconds

    Returns
    -------
    tuple
        (success: bool, error_msg: str)
    """
    api = None
    try:
        tq_config = config.tq
        auth = TqAuth(tq_config['username'], tq_config['password'])

        # Create account object based on run mode
        if config.run_mode == 'real':
            account = TqKq()
        else:
            account = TqKq()

        # Connect to TqApi with timeout
        api = TqApi(account=account, auth=auth)

        # Wait for initial data with timeout
        # TqApi uses wait_update() which blocks until data arrives
        # We'll do a simple check by trying to get account info
        start_time = 0
        max_attempts = timeout

        for _ in range(max_attempts):
            api.wait_update(deadline=1)  # Wait 1 second per attempt
            account_obj = api.get_account()
            if account_obj:
                break

        if not account_obj:
            raise TimeoutError("Failed to retrieve account data within timeout")

        api.close()

        logger.info(f"✓ TqSDK connection OK (user: {tq_config['username']})")
        return True, ""

    except Exception as e:
        error_msg = f"TqSDK connection failed: {e}"
        logger.error(error_msg)

        # Clean up API connection if it was created
        if api:
            try:
                api.close()
            except:
                pass

        return False, error_msg


def check_all_connections(config: Config, timeout: int = 5) -> bool:
    """
    Check all required connections

    Parameters
    ----------
    config : Config
        Configuration instance
    timeout : int
        Connection timeout in seconds for each check

    Returns
    -------
    bool
        True if all connections succeed
    """
    logger.info("=" * 60)
    logger.info("Starting connection pre-flight checks...")
    logger.info("=" * 60)

    checks = [
        ("Redis", check_redis_connection),
        ("PostgreSQL", check_postgres_connection),
        ("RabbitMQ", check_rabbitmq_connection),
        ("TqSDK", check_tqsdk_connection)
    ]

    all_ok = True
    for name, check_func in checks:
        logger.info(f"Checking {name} connection...")
        success, error_msg = check_func(config, timeout)

        if not success:
            logger.error(f"✗ {name} check failed: {error_msg}")
            all_ok = False

    if all_ok:
        logger.info("=" * 60)
        logger.info("✓ All connection checks passed")
        logger.info("=" * 60)
    else:
        logger.error("=" * 60)
        logger.error("✗ Some connection checks failed")
        logger.error("=" * 60)

    return all_ok
