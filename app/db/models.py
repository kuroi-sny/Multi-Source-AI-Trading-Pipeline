from sqlalchemy import Column, Integer, String, Float
from app.db.database import Base
from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey
import datetime



class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    email = Column(String, nullable=True)




class TradeAnalysis(Base):
    __tablename__ = "trade_analyses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True) 
    symbol = Column(String, index=True)
    sentiment = Column(String)
    reasoning = Column(String)
    embedding = Column(Vector(3072))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))

    