"""
Example of code
Copyright © 2022. All Rights are Reserved by Maria Chichkan
"""

import sys
import datetime
import asyncio
import pandas as pd
import aioredis
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, "../utils")
from db_orm import TradingPrices
from settings import (
    REDIS_CLIENT,
    PSQL_CLIENT,
    PSQL_DB,
    REDIS_RETENTION_PERIOD,
    _logging,
)


class DBUpdater:
    """
    This class updates table, which stores historical data of trading instruments prices.
    The table is updated with Redis Time Series data.
    """
    def __init__(self):
        """Get Redis and Postgresql clients and logger"""
        # Redis client bound to pool of connections (auto-reconnecting).
        redis_url = f"redis://{REDIS_CLIENT.HOST}:{REDIS_CLIENT.PORT}"
        self.__redis_session = aioredis.from_url(
            redis_url,
            password=REDIS_CLIENT.PASSWORD,
            encoding="utf-8",
            decode_responses=True,
        )

        psql_url = (
            f"postgresql+asyncpg://{PSQL_CLIENT.USER}:{PSQL_CLIENT.PASSWORD}@"
            + f"{PSQL_CLIENT.HOST}"
            + f"{':'+ PSQL_CLIENT.PORT if not PSQL_CLIENT.PORT in ['False', False] else ''}"
            + f"/{PSQL_DB}"
        )

        psql_engine = create_async_engine(psql_url, echo=True)
        self.__psql_session = sessionmaker(
            psql_engine, expire_on_commit=False, class_=AsyncSession
        )
        self.logger = _logging()

    async def get_latest_prices(self):
        """Get latest instrument prices from Redis time series"""
        current_time = int(datetime.datetime.now().timestamp() * 1000)
        # Get all trading_instruments data from redis for the last few minutes
        # (1 minute is 60 000 ms)
        timeseries = await self.__redis_session.execute_command(
            "TS.MRANGE",
            current_time - REDIS_RETENTION_PERIOD * 60000,
            current_time,
            "FILTER",
            "type=trading_instruments",
        )
        self.logger.info(
            f"Got instrument prices from Redis for the last {REDIS_RETENTION_PERIOD} minutes"
        )
        ts_lst = []
        for timeseries_ in timeseries:
            df_ts = pd.DataFrame(timeseries_[2], columns=["created_at", "price"])
            df_ts["instrument_id"] = timeseries_[0]
            ts_lst.append(df_ts)
        df_latest_prices = pd.concat(ts_lst)
        df_latest_prices["price"] = df_latest_prices["price"].astype("int")
        df_latest_prices["created_at"] = pd.to_datetime(
            df_latest_prices["created_at"], unit="ms"
        )
        return df_latest_prices

    async def save_latest_prices(self, df_latest_prices):
        """Save current trading data to database"""
        if df_latest_prices.shape[0] == 0:  # no new data
            self.logger.info(
                f"No new data for the last {REDIS_RETENTION_PERIOD} minutes"
            )
            return
        cols = list(
            set(df_latest_prices.columns.to_list())
            & set(TradingPrices.__table__.columns.keys())
        )
        df_latest_prices = df_latest_prices[cols]
        insert_stmt = insert(TradingPrices).values(
            df_latest_prices.to_dict(orient="records")
        )
        on_update_stmt = insert_stmt.on_conflict_do_nothing(
            index_elements=[
                TradingPrices.__table__.columns.instrument_id,
                TradingPrices.__table__.columns.created_at,
            ]
        )
        async with self.__psql_session() as session:
            await session.execute(on_update_stmt)
            await session.commit()
            self.logger.info("Updated database with the latest data")

    async def update_trading_prices(self):
        """Get and save current trading data to database every minute"""
        while True:
            # As the order is important
            df_latest_prices = await self.get_latest_prices()
            await self.save_latest_prices(df_latest_prices)
            await asyncio.sleep(60)


def main():
    db_updater = DBUpdater()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(db_updater.update_trading_prices())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    loop.close()


if __name__ == "__main__":
    main()
