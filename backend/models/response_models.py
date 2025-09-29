from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from .request_models import DocumentType, ProcessingStatus, DataSource

class SourceInfo(BaseModel):
    document_id: str
    document_name: str
    page_number: Optional[int]
    section: Optional[str]
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    content_preview: Optional[str] = Field(None, max_length=250)

class QueryResponse(BaseModel):
    answer: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: List[SourceInfo]
    query_time_ms: int
    model_used: str

class BatchQueryResponse(BaseModel):
    results: List[QueryResponse]
    total_time_ms: int

class DocumentInfo(BaseModel):
    id: str
    filename: str
    original_name: str
    file_size: int
    upload_date: datetime
    document_type: Optional[DocumentType]
    product_family: Optional[str]
    product_model: Optional[str]
    version: Optional[str]
    language: str
    page_count: Optional[int]
    processing_status: ProcessingStatus
    created_at: datetime
    updated_at: datetime

class DocumentDetail(BaseModel):
    document: DocumentInfo
    sections: List[Dict[str, Any]]
    specifications: List[Dict[str, Any]]

class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]
    total: int
    page: int
    limit: int
    total_pages: int

class UploadResponse(BaseModel):
    document_id: str
    status: ProcessingStatus
    message: str
    file_info: Optional[Dict[str, Any]] = None

class StatusResponse(BaseModel):
    ollama_status: str
    vector_db_status: str
    documents_count: int
    vector_count: int
    system_health: str

class StatisticsResponse(BaseModel):
    total_queries: int
    avg_response_time_ms: float
    popular_queries: List[str]
    user_role_distribution: Dict[str, int]
    documents_by_type: Dict[str, int]

class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    uptime_seconds: int

class ReindexResponse(BaseModel):
    status: str
    message: str
    processed_documents: int
    failed_documents: int
    processing_time_ms: int

class MultiSourceInfo(BaseModel):
    source_type: DataSource
    source_id: str
    content: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # 소스별 특화 정보
    document_name: Optional[str] = None  # 문서 소스용
    page_number: Optional[int] = None    # 문서 소스용
    section: Optional[str] = None        # 문서 소스용
    url: Optional[str] = None           # 웹 검색용
    web_source: Optional[str] = None    # 웹 검색용

class MultiSourceQueryResponse(BaseModel):
    answer: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: List[MultiSourceInfo]
    query_time_ms: int
    model_used: str

    # 소스별 통계
    sources_by_type: Dict[DataSource, int] = Field(default_factory=dict)
    search_strategy: str
    total_sources_searched: int

class SourceSearchResult(BaseModel):
    source_type: DataSource
    results: List[MultiSourceInfo]
    search_time_ms: int
    total_found: int
    status: str  # "success", "partial", "failed"
    error_message: Optional[str] = None

class MultiSourceSearchResponse(BaseModel):
    question: str
    source_results: List[SourceSearchResult]
    combined_answer: Optional[str] = None
    total_search_time_ms: int
    successful_sources: int
    failed_sources: int

class WebSearchResult(BaseModel):
    title: str
    content: str
    url: str
    source: str
    type: str  # "instant_answer", "organic", "knowledge_graph", etc.
    relevance_score: float

class DatabaseSearchResult(BaseModel):
    id: str
    source_type: str  # "document_metadata", "query_history"
    content: str
    similarity: float
    metadata: Dict[str, Any]