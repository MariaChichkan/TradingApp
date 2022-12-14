"""
Database ORM classes for TradingApp project
Copyright © 2022. All Rights are Reserved by Maria Chichkan
"""
from sqlalchemy.dialects.postgresql import INTEGER, VARCHAR, TIMESTAMP
from sqlalchemy import Column
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class TradingPrices(Base):
    """Table with historical trading prices"""
    __tablename__ = 'trading_prices'
    instrument_id = Column('instrument_id', VARCHAR(50), primary_key=True)
    created_at = Column('created_at', TIMESTAMP, primary_key=True)
    price = Column('price', INTEGER)

