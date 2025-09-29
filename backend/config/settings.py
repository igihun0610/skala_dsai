from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Application
    app_name: str = "Manufacturing DataSheet RAG System"
    app_version: str = "1.0.0"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/metadata.db"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2:0.5b"
    ollama_timeout: int = 120

    # Vector Database
    vector_db_path: str = "./data/vectordb"
    embedding_model: str = "BAAI/bge-m3"
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # File Storage
    upload_path: str = "./data/uploads"
    processed_path: str = "./data/processed"
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_extensions: list = [".pdf"]

    # RAG Settings
    max_context_length: int = 4000
    top_k_retrieval: int = 5
    temperature: float = 0.1

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = "./logs/app.log"

    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()