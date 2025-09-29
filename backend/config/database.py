from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean
from datetime import datetime
from .settings import settings

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

# Database Models
class Document(Base):
    __tablename__ = "documents"

    id = Column(String(255), primary_key=True)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    upload_date = Column(DateTime, default=datetime.utcnow)
    document_type = Column(String(100))  # datasheet, manual, specification
    product_family = Column(String(100))
    product_model = Column(String(100))
    version = Column(String(50))
    language = Column(String(10), default='ko')
    page_count = Column(Integer)
    processing_status = Column(String(50), default='pending')  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DocumentSection(Base):
    __tablename__ = "document_sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(255), nullable=False)
    section_title = Column(String(255))
    section_type = Column(String(100))  # overview, specifications, electrical, mechanical, environmental
    page_number = Column(Integer)
    start_position = Column(Integer)
    end_position = Column(Integer)
    content_preview = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class Specification(Base):
    __tablename__ = "specifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(255), nullable=False)
    section_id = Column(Integer)
    parameter_name = Column(String(255))
    parameter_value = Column(String(255))
    unit = Column(String(50))
    condition_text = Column(Text)
    min_value = Column(Float)
    max_value = Column(Float)
    typical_value = Column(Float)
    page_number = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class VectorChunk(Base):
    __tablename__ = "vector_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(255), nullable=False)
    chunk_index = Column(Integer)
    chunk_text = Column(Text)
    chunk_embedding_id = Column(String(100))  # FAISS index ID
    page_number = Column(Integer)
    section_id = Column(Integer)
    token_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_role = Column(String(50))
    query_text = Column(Text)
    response_text = Column(Text)
    retrieved_documents = Column(Text)  # JSON array of document IDs
    response_time_ms = Column(Integer)
    rating = Column(Integer)  # 1-5 user feedback
    created_at = Column(DateTime, default=datetime.utcnow)

# Dependency to get DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Initialize database
async def init_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)