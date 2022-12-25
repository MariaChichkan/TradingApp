"""
Example of code.
Database credentials and some other private information are stored in .env file.
Please, contact your system administrator to configure TradingApp project
Copyright © 2022. All Rights are Reserved by Maria Chichkan
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pydantic import BaseSettings



class RedisCredentials(BaseSettings):
    """Host, Port and Credentials to connect Redis"""
    HOST = os.environ.get("REDIS_HOST")
    PORT = os.environ.get("REDIS_PORT")
    PASSWORD = os.environ.get("REDIS_PASSWORD")


class PostgreSQLCredentials(BaseSettings):
    """Host, Port and Credentials to connect PostgreSQL"""
    HOST = os.environ.get("PSQL_HOST")
    PORT = os.environ.get("PSQL_PORT")
    USER = os.environ.get("PSQL_USER")
    PASSWORD = os.environ.get("PSQL_PASSWORD")


REDIS_CLIENT = RedisCredentials()
# period in minutes for which we store data for time series, by default it is 5 minutes
REDIS_RETENTION_PERIOD = os.environ.get("REDIS_RETENTION_PERIOD", 5)
PSQL_CLIENT = PostgreSQLCredentials()
PSQL_DB = os.environ.get("PSQL_DB")

# In future the best approach will be to move this information to the database table
TRADING_INSTRUMENTS_WITH_NAMES = {
    "ticker_999": "Tesla",
    "ticker_998": "Gold",
    "ticker_997": "Apple",
}
TRADING_INSTRUMENTS = list(TRADING_INSTRUMENTS_WITH_NAMES.keys())


def _logging():
    """
    This function will create or update logfile and save it
    to "logs" folder (it will create this folder if not exists).
    """
    parent_dir = r"%s" % os.path.split(os.getcwd())[0].replace("\\", "/")
    log_dir = "/".join([parent_dir, "logs"])
    project_name = os.path.split(os.getcwd())[1]
    filename = f"{log_dir}/{project_name}.log"

    # Create folder for all logs if not exists
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir)

    # Create Logger
    logger = logging.getLogger(project_name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        # Create handler to write logs to file
        # RotatingFileHandler controls maximum file size and keeps only the last logs
        logger_handler = RotatingFileHandler(
            filename,
            maxBytes=50 * 1024 * 1024,
            backupCount=2,
            encoding=None,
            delay=False,
        )
        # logger_handler = logging.FileHandler(filename)
        logger_handler.setLevel(logging.INFO)
        # Create Formatter to format messages in log
        logger_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        logger_formatter.datefmt = "%Y-%m-%d %H:%M:%S"
        # Add Formatter to handler
        logger_handler.setFormatter(logger_formatter)
        # Add handler to Logger
        logger.addHandler(logger_handler)
    return logger
