﻿import sys
sys.path.insert(0, "../utils")

import asyncio
import aioredis
import json
from datetime import datetime
from random import random

from settings import REDIS_CLIENT, TRADING_INSTRUMENTS


class PriceGenerator:
    def __init__(self, trading_instruments: list):
        # Redis client bound to pool of connections (auto-reconnecting).
        self.__redis_url = f"redis://{REDIS_CLIENT.HOST}:{REDIS_CLIENT.PORT}"
        self.redis = aioredis.from_url(self.__redis_url, password=REDIS_CLIENT.PASSWORD,
                                       encoding='utf-8', decode_responses=True)
        self.trading_instruments = trading_instruments
        self.trading_prices = {instr: 0 for instr in trading_instruments}

    async def subscribe(self):
        pubsub = self.redis.pubsub()
        for instr in self.trading_instruments:
            await pubsub.psubscribe(instr)

    @staticmethod
    def generate_movement():
        movement = -1 if random() < 0.5 else 1
        return movement

    async def generate_trading_price(self, instrument):
        while True:
            if instrument not in self.trading_prices.keys():
                self.trading_prices[instrument] = 0
            # Get current price of a trading instrument
            self.trading_prices[instrument] += self.generate_movement()
            current_time = int(datetime.now().timestamp() * 1000)
            # Add new value for Redis Time Series of a trading instrument
            # 60000 ms equals 1 minute - the data is stored in Redis for the period of 5 minutes
            ts = await self.redis.execute_command("TS.ADD", instrument, current_time, self.trading_prices[instrument],
                                                  'RETENTION', 300000, 'ON_DUPLICATE', 'FIRST', 'LABELS', 'name', instrument, 'type', 'trading_instruments' )

            res = await self.redis.publish(instrument, json.dumps({"time": current_time,"value": self.trading_prices[instrument]}))
            sleep_interval = (1000 - (int(datetime.now().timestamp() * 1000) - current_time)) / 1000
            await asyncio.sleep(sleep_interval if sleep_interval > 0 else 0)


async def main():
    price_generator = PriceGenerator(TRADING_INSTRUMENTS)
    await price_generator.subscribe()
    tasks = []
    for instrument in TRADING_INSTRUMENTS:
        tasks.append(asyncio.create_task(price_generator.generate_trading_price(instrument)))
    res = await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == '__main__':
    asyncio.run(main())
