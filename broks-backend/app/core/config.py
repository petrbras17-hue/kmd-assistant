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
