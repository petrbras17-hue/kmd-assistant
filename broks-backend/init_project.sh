#!/bin/bash

echo "🚀 Initializing BROKS Backend MVP structure..."

# 1. Создаем папки
mkdir -p app/api
mkdir -p app/core
mkdir -p app/models
mkdir -p app/services
mkdir -p alembic/versions

# 2. Конфигурация
cat <<EOCONF > app/core/config.py
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "BROKS Platform API"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@db:5432/broks")
    
    # API Keys (заглушки)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    REPLICATE_API_TOKEN: str = os.getenv("REPLICATE_API_TOKEN", "")
    
    class Config:
        case_sensitive = True

settings = Settings()
EOCONF

# 3. Модели базы данных (Sprint 1)
cat <<EODB > app/models/database.py
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
EODB

# 4. Сервисы

# --- Sprint 1: Valuation ---
cat <<EOVAL > app/services/valuation.py
import pandas as pd
from sklearn.ensemble import IsolationForest
from typing import List, Dict

class ValuationService:
    def __init__(self):
        self.outlier_detector = IsolationForest(contamination=0.05, random_state=42)

    def estimate_price(self, target_area: float, comps: List[Dict]) -> dict:
        if not comps:
            return {"error": "No data"}
        
        df = pd.DataFrame(comps)
        df['price_per_sqm'] = df['price'] / df['area']
        
        avg_sqm = df['price_per_sqm'].mean()
        recommended = avg_sqm * target_area
        
        return {
            "recommended_price": int(recommended),
            "range_min": int(recommended * 0.9),
            "range_max": int(recommended * 1.1)
        }
EOVAL

# --- Sprint 2: Renovation ---
cat <<EOREN > app/services/renovation.py
import replicate
from app.core.config import settings

class RenovationService:
    def __init__(self):
        self.client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)
        self.model = "jagilley/controlnet-mlsd-1.5:69ed025f1b79a1d2488b928d3a77e314f10e797297c458f4432155c49442439a"

    def renovate(self, image_url: str, prompt: str) -> str:
        # Заглушка логики вызова
        return "https://replicate.com/api/models/predictions/output.jpg"
EOREN

# --- Sprint 3: Video ---
cat <<EOVID > app/services/video.py
import os

class VideoComposer:
    def create_reel(self, avatar_path: str, photos: list, audio_path: str, output_path: str):
        print(f"Simulating rendering video to {output_path}...")
        return True
EOVID

# 5. API Endpoints
cat <<EOAPI > app/api/endpoints.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.services.valuation import ValuationService
from app.services.renovation import RenovationService

router = APIRouter()

class ValuationRequest(BaseModel):
    area: float
    comparables: list[dict]

@router.post("/valuation/estimate")
def estimate_price(req: ValuationRequest):
    service = ValuationService()
    return service.estimate_price(req.area, req.comparables)

@router.post("/ai/renovate")
def renovate_room(image_url: str, style: str):
    service = RenovationService()
    return service.renovate(image_url, f"{style} interior")

@router.get("/voice/availability")
def check_availability(listing_id: str, date: str):
    return {"available": True, "slots": ["14:00", "16:00"]}
EOAPI

# 6. Main App
cat <<EOMAIN > app/main.py
from fastapi import FastAPI
from app.api.endpoints import router

app = FastAPI(title="BROKS Platform", version="2.0.0")
app.include_router(router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok", "system": "BROKS Backend"}
EOMAIN

# 7. Docker и зависимости
cat <<EOREQ > requirements.txt
fastapi
uvicorn
sqlalchemy
psycopg2-binary
pgvector
pydantic-settings
pandas
scikit-learn
replicate
moviepy
alembic
EOREQ

cat <<EODOCK > docker-compose.yml
version: '3.8'

services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: broks
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/broks
    depends_on:
      - db

volumes:
  postgres_data:
EODOCK

cat <<EODF > Dockerfile
FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y ffmpeg libsm6 libxext6 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EODF

cat <<EOGIT > .gitignore
__pycache__/
*.pyc
.env
venv/
.DS_Store
postgres_data/
temp_assets/
EOGIT

echo "✅ Файлы проекта созданы!"
