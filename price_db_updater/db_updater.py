import sys
sys.path.insert(0, "../utils")

import aioredis
import datetime
import asyncio
import pandas as pd

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from settings import REDIS_CLIENT, PSQL_CLIENT, PSQL_DB
from db_orm import TradingPrices


class DBUpdater:
    def __init__(self):
        # Redis client bound to pool of connections (auto-reconnecting).
        redis_url = f"redis://{REDIS_CLIENT.HOST}:{REDIS_CLIENT.PORT}"
        self.redis = aioredis.from_url(redis_url, password=REDIS_CLIENT.PASSWORD,
                                       encoding='utf-8', decode_responses=True)

        psql_url = \
            f"postgresql+asyncpg://{PSQL_CLIENT.USER}:{PSQL_CLIENT.PASSWORD}@"+ \
            f"{PSQL_CLIENT.HOST}{':'+ PSQL_CLIENT.PORT if PSQL_CLIENT.PORT else ''}"+ \
            f"/{PSQL_DB}"

        psql_engine = create_async_engine(psql_url, echo=True)
        self.psql_Session = sessionmaker(psql_engine, expire_on_commit=False, class_=AsyncSession)

    # Get latest instrument prices from Redis time series
    async def get_latest_prices(self):
        current_time = int(datetime.datetime.now().timestamp() * 1000)
        # Get all trading_instruments data from redis  for the period of the 5 minutes (300000 ms)
        ts = await self.redis.execute_command("TS.MRANGE", current_time - 300000, current_time, 'FILTER', 'type=trading_instruments')
        df_lst = []
        for timeseries in ts:
            df = pd.DataFrame(timeseries[2], columns=["created_at", 'price'])
            df["instrument_id"] = timeseries[0]
            df_lst.append(df)
        df_latest_prices = pd.concat(df_lst)
        df_latest_prices['price'] = df_latest_prices['price'].astype("int")
        df_latest_prices["created_at"] = pd.to_datetime(df_latest_prices["created_at"], unit='ms')
        return df_latest_prices

    # Save current data to DB
    async def save_latest_prices(self, df_latest_prices):
        if df_latest_prices.shape[0] == 0: # no new data
            return
        cols = list(set(df_latest_prices.columns.to_list()) & set(TradingPrices.__table__.columns.keys()))
        df_latest_prices = df_latest_prices[cols]
        insert_stmt = insert(TradingPrices).values(df_latest_prices.to_dict(orient='records'))
        on_update_stmt = insert_stmt.on_conflict_do_nothing(
            index_elements=[TradingPrices.__table__.columns.instrument_id, TradingPrices.__table__.columns.created_at])
        async with self.psql_Session() as session:
            result = await session.execute(on_update_stmt)
            await session.commit()

    async def update_trading_prices(self):
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


if __name__ == '__main__':
    main()


