from sqlalchemy import Column, UUID, String, Float, Integer, ForeignKey, JSON, DateTime, Boolean, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pgvector.sqlalchemy import Vector
from app.core.config import settings
import uuid
import datetime

Base = declarative_base()

class Demand(Base):
    __tablename__ = 'demands'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    budget_min = Column(Integer, nullable=True)
    budget_max = Column(Integer, nullable=True)
    area_min = Column(Float, nullable=True)
    area_max = Column(Float, nullable=True)
    search_text = Column(String)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Match(Base):
    __tablename__ = 'matches'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(UUID(as_uuid=True), nullable=False)
    demand_id = Column(UUID(as_uuid=True), ForeignKey('demands.id'))
    score = Column(Float)
    status = Column(String, default='new')

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
