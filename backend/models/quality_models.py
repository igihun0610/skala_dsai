from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class ValidationResult(BaseModel):
    """답변 검증 결과"""
    is_valid: bool = Field(..., description="답변 유효성")
    quality_score: float = Field(..., ge=0.0, le=1.0, description="품질 점수 (0-1)")
    issues: List[str] = Field(default=[], description="발견된 문제점들")
    suggestions: List[str] = Field(default=[], description="개선 제안")
    confidence_adjusted: float = Field(..., ge=0.0, le=1.0, description="조정된 신뢰도")
    validation_details: Dict[str, Any] = Field(default={}, description="상세 검증 정보")


class SelfTestCase(BaseModel):
    """셀프 테스트 케이스"""
    question: str = Field(..., description="테스트 질문")
    expected_answer: Optional[str] = Field(None, description="기대되는 답변")
    expected_validation: bool = Field(True, description="유효한 답변을 기대하는지 여부")
    test_type: str = Field("general", description="테스트 유형")
    description: str = Field("", description="테스트 설명")


class SelfTestRequest(BaseModel):
    """셀프 테스트 요청"""
    test_suite: str = Field(..., description="테스트 스위트 이름")
    custom_cases: Optional[List[SelfTestCase]] = Field(None, description="커스텀 테스트 케이스들")


class SelfTestResult(BaseModel):
    """셀프 테스트 결과"""
    test_id: int = Field(..., description="테스트 ID")
    question: str = Field(..., description="테스트 질문")
    expected_answer: str = Field("", description="기대 답변")
    actual_answer: str = Field("", description="실제 답변")
    expected_validation: bool = Field(..., description="기대 검증 결과")
    passed: bool = Field(..., description="테스트 통과 여부")
    validation_result: Optional[ValidationResult] = Field(None, description="검증 결과")


class SelfTestSummary(BaseModel):
    """셀프 테스트 요약"""
    total_tests: int = Field(..., description="총 테스트 수")
    passed: int = Field(..., description="통과한 테스트 수")
    failed: int = Field(..., description="실패한 테스트 수")
    overall_score: float = Field(..., ge=0.0, le=1.0, description="전체 점수")
    test_results: List[SelfTestResult] = Field(..., description="테스트 결과들")
    timestamp: str = Field(..., description="테스트 실행 시간")


class QualityCheckRequest(BaseModel):
    """품질 검사 요청"""
    question: str = Field(..., description="질문")
    answer: str = Field(..., description="답변")
    sources: List[Dict[str, Any]] = Field(default=[], description="소스 정보")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="신뢰도")


class DebugInfo(BaseModel):
    """디버그 정보"""
    vectorstore_stats: Dict[str, Any] = Field(..., description="벡터스토어 통계")
    system_status: Dict[str, Any] = Field(..., description="시스템 상태")
    performance_metrics: Dict[str, Any] = Field(..., description="성능 지표")
    error_logs: List[Dict[str, Any]] = Field(default=[], description="에러 로그")


class SystemStats(BaseModel):
    """시스템 통계"""
    documents_count: int = Field(..., description="문서 수")
    vector_chunks_count: int = Field(..., description="벡터 청크 수")
    queries_count: int = Field(..., description="질의 수")
    average_response_time: float = Field(..., description="평균 응답 시간")
    system_uptime: str = Field(..., description="시스템 가동 시간")
    memory_usage: Dict[str, Any] = Field(..., description="메모리 사용량")


class VectorStoreInfo(BaseModel):
    """벡터스토어 정보"""
    name: str = Field(..., description="벡터스토어 이름")
    loaded: bool = Field(..., description="로드 여부")
    document_count: Optional[int] = Field(None, description="문서 수")
    index_size: Optional[int] = Field(None, description="인덱스 크기")
    sample_content: Optional[str] = Field(None, description="샘플 내용")
    embedding_model: Optional[str] = Field(None, description="임베딩 모델")


class PerformanceMetrics(BaseModel):
    """성능 지표"""
    queries_per_minute: float = Field(..., description="분당 질의 수")
    average_query_time: float = Field(..., description="평균 질의 시간")
    vector_search_time: float = Field(..., description="벡터 검색 시간")
    llm_response_time: float = Field(..., description="LLM 응답 시간")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="성공률")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="에러율")


class ErrorLog(BaseModel):
    """에러 로그"""
    timestamp: datetime = Field(..., description="발생 시간")
    level: str = Field(..., description="로그 레벨")
    message: str = Field(..., description="에러 메시지")
    traceback: Optional[str] = Field(None, description="스택 트레이스")
    context: Dict[str, Any] = Field(default={}, description="컨텍스트 정보")


class HealthCheckDetail(BaseModel):
    """상세 헬스체크 정보"""
    component: str = Field(..., description="컴포넌트 이름")
    status: str = Field(..., description="상태")
    response_time: float = Field(..., description="응답 시간")
    details: Dict[str, Any] = Field(default={}, description="상세 정보")
    last_check: datetime = Field(..., description="마지막 체크 시간")