from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class UserRole(str, Enum):
    ENGINEER = "engineer"
    QUALITY = "quality"
    SALES = "sales"
    SUPPORT = "support"

class DocumentType(str, Enum):
    DATASHEET = "datasheet"
    MANUAL = "manual"
    SPECIFICATION = "specification"

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DocumentUploadRequest(BaseModel):
    document_type: Optional[DocumentType] = DocumentType.DATASHEET
    product_family: Optional[str] = None
    product_model: Optional[str] = None
    version: Optional[str] = None
    language: str = "ko"

class QueryRequest(BaseModel):
    question: str = Field(..., description="질문 내용", min_length=1, max_length=1000)
    user_role: UserRole = Field(UserRole.ENGINEER, description="사용자 역할")
    document_filter: Optional[Dict[str, Any]] = Field(
        None,
        description="문서 필터링 조건"
    )
    top_k: int = Field(5, ge=1, le=20, description="검색할 결과 수")

class DocumentFilter(BaseModel):
    document_types: Optional[List[DocumentType]] = None
    product_families: Optional[List[str]] = None
    models: Optional[List[str]] = None
    date_from: Optional[str] = None  # ISO date string
    date_to: Optional[str] = None

class BatchQueryRequest(BaseModel):
    queries: List[QueryRequest] = Field(..., max_items=10)

class DocumentListRequest(BaseModel):
    page: int = Field(1, ge=1, description="페이지 번호")
    limit: int = Field(20, ge=1, le=100, description="페이지 당 항목 수")
    document_type: Optional[DocumentType] = None
    product_family: Optional[str] = None
    search: Optional[str] = Field(None, max_length=200, description="검색어")

class ReindexRequest(BaseModel):
    document_ids: Optional[List[str]] = Field(None, description="재인덱싱할 문서 ID 목록")
    force: bool = Field(False, description="강제 재인덱싱 여부")

class DataSource(str, Enum):
    DOCUMENTS = "documents"
    DATABASE = "database"
    WEB_SEARCH = "web_search"

class MultiSourceQueryRequest(BaseModel):
    question: str = Field(..., description="질문 내용", min_length=1, max_length=1000)
    user_role: UserRole = Field(UserRole.ENGINEER, description="사용자 역할")
    data_sources: List[DataSource] = Field(
        [DataSource.DOCUMENTS],
        description="검색할 데이터 소스 목록"
    )
    document_filter: Optional[Dict[str, Any]] = Field(
        None,
        description="문서 필터링 조건"
    )
    top_k_per_source: int = Field(3, ge=1, le=10, description="소스별 검색할 결과 수")
    enable_web_search: bool = Field(False, description="웹 검색 활성화 여부")
    web_search_query: Optional[str] = Field(None, description="웹 검색용 쿼리 (자동 생성 시 None)")
    combine_results: bool = Field(True, description="결과 통합 여부")

class SourceWeight(BaseModel):
    documents: float = Field(0.6, ge=0.0, le=1.0, description="문서 검색 가중치")
    database: float = Field(0.3, ge=0.0, le=1.0, description="DB 검색 가중치")
    web_search: float = Field(0.1, ge=0.0, le=1.0, description="웹 검색 가중치")

class AdvancedMultiSourceRequest(BaseModel):
    question: str = Field(..., description="질문 내용", min_length=1, max_length=1000)
    user_role: UserRole = Field(UserRole.ENGINEER, description="사용자 역할")
    data_sources: List[DataSource] = Field(
        [DataSource.DOCUMENTS],
        description="검색할 데이터 소스 목록"
    )
    source_weights: Optional[SourceWeight] = Field(None, description="소스별 가중치")
    top_k_per_source: int = Field(3, ge=1, le=10, description="소스별 검색할 결과 수")
    min_relevance_threshold: float = Field(0.3, ge=0.0, le=1.0, description="최소 관련성 임계값")
    enable_web_search: bool = Field(False, description="웹 검색 활성화 여부")
    web_search_engine: Optional[str] = Field("duckduckgo", description="웹 검색 엔진")
    manufacturing_focus: bool = Field(True, description="제조업 특화 검색 여부")
    document_filter: Optional[Dict[str, Any]] = Field(None, description="문서 필터링 조건")