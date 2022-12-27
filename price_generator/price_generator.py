"""
Example of code
Copyright © 2022. All Rights are Reserved by Maria Chichkan
"""

import sys
import asyncio
import json
from datetime import datetime
from random import random
import aioredis
sys.path.insert(0, "../utils")
from settings import REDIS_CLIENT, TRADING_INSTRUMENTS, REDIS_RETENTION_PERIOD, _logging


class PriceGenerator:
    """
    This class generates prices of trading instruments and sends them to Redis
    """
    def __init__(self, trading_instruments: list):
        """
        Args:
            trading_instruments: list
        """
        # Redis client bound to pool of connections (auto-reconnecting).
        self.__redis_url = f"redis://{REDIS_CLIENT.HOST}:{REDIS_CLIENT.PORT}"
        self.redis = aioredis.from_url(
            self.__redis_url,
            password=REDIS_CLIENT.PASSWORD,
            encoding="utf-8",
            decode_responses=True,
        )
        self.trading_instruments = trading_instruments
        self.trading_prices = {instr: 0 for instr in trading_instruments}
        self.logger = _logging()

    async def subscribe(self):
        """Subscribe to all trading instruments, listed in settings"""
        try:
            pubsub = self.redis.pubsub()
            for instr in self.trading_instruments:
                await pubsub.psubscribe(instr)
                self.logger.info(f"Subscribed to instrument {instr}")
        except Exception as ex:
            self.logger.error(ex)

    @staticmethod
    def generate_movement():
        """Let's imagine that the price of a trading instrument changes randomly by 1"""
        movement = -1 if random() < 0.5 else 1
        return movement

    async def generate_trading_price(self, instrument):
        """
        This function calculates a new price for the trading instrument every second,
        publishes it to Redis channel with the name equals to the instrument's name
        and also saves it to the Redis Time Series with the name equals to the instrument's name
        Args:
            instrument: string
        """
        while True:
            try:
                if instrument not in self.trading_prices.keys():
                    self.trading_prices[instrument] = 0
                # Get current price of a trading instrument
                self.trading_prices[instrument] += self.generate_movement()
                self.logger.info(
                    f"Instrument {instrument} has price {self.trading_prices[instrument]}"
                )
                current_time = int(datetime.now().timestamp() * 1000)
                # Add new value for Redis Time Series of a trading instrument
                # 60000 ms equals 1 minute
                await self.redis.execute_command(
                    "TS.ADD",
                    instrument,
                    current_time,
                    self.trading_prices[instrument],
                    "RETENTION",
                    REDIS_RETENTION_PERIOD * 60000,
                    "ON_DUPLICATE",
                    "FIRST",
                    "LABELS",
                    "name",
                    instrument,
                    "type",
                    "trading_instruments",
                )

                await self.redis.publish(
                    instrument,
                    json.dumps(
                        {"time": current_time, "value": self.trading_prices[instrument]}
                    ),
                )
                sleep_interval = (
                    1000 - (int(datetime.now().timestamp() * 1000) - current_time)
                ) / 1000
                # New price have to be sent every second
                await asyncio.sleep(sleep_interval if sleep_interval > 0 else 0)
            except Exception as ex:
                self.logger.error(
                    f"{ex} while updating price for instrument {instrument}"
                )


async def main():
    """Generate and save trading instruments prices to Redis cache"""
    price_generator = PriceGenerator(TRADING_INSTRUMENTS)
    await price_generator.subscribe()
    tasks = []
    for instrument in TRADING_INSTRUMENTS:
        tasks.append(price_generator.generate_trading_price(instrument))
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
