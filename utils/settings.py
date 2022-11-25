import os
import logging
from pydantic import BaseSettings


class RedisCredentials(BaseSettings):
    HOST = os.environ.get("REDIS_HOST")
    PORT = os.environ.get("REDIS_PORT")
    PASSWORD = os.environ.get("REDIS_PASSWORD")


class PostgreSQLCredentials(BaseSettings):
    HOST = os.environ.get("PSQL_HOST")
    PORT = os.environ.get("PSQL_PORT")
    USER = os.environ.get("PSQL_USER")
    PASSWORD = os.environ.get("PSQL_PASSWORD")


REDIS_CLIENT = RedisCredentials()
PSQL_CLIENT = PostgreSQLCredentials()

PSQL_DB = os.environ.get("PSQL_DB")

# In future the best approach will be to move this information to the database table
TRADING_INSTRUMENTS_WITH_NAMES = {"ticker_999": "Tesla", "ticker_998": "Gold", "ticker_997": "Apple"}
TRADING_INSTRUMENTS = list(TRADING_INSTRUMENTS_WITH_NAMES.keys())


# def start_logging(loggername):
#     path = r'%s' % os.getcwd().replace('\\', '/')
#     filename = path+f'/{loggername}.log'
#     logger = logging.getLogger(loggername)
#     logger.setLevel(logging.INFO)
#     if not logger.handlers:
#         fh = logging.FileHandler(filename)
#         fh.setLevel(logging.INFO)
#         logger.addHandler(fh)
#
#     # start_time = datetime.datetime.now().replace(microsecond=0)
#     # logger.info(f'Today: {str(start_time)} starting logging')
#     return logger