from sqlalchemy.dialects.postgresql import INTEGER, VARCHAR, TIMESTAMP
from sqlalchemy import Column
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class TradingPrices(Base):
    __tablename__ = 'trading_prices'
    instrument_id = Column('instrument_id', VARCHAR(50), primary_key=True)
    created_at = Column('created_at', TIMESTAMP, primary_key=True)
    price = Column('price', INTEGER)

    def __init__(self, instrument_id, created_at, price):
        self.instrument_id = instrument_id
        self.created_at = created_at
        self.price = price
