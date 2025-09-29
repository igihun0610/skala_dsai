import asyncio
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from ..models.request_models import (
    MultiSourceQueryRequest,
    AdvancedMultiSourceRequest,
    DataSource,
    UserRole
)
from ..models.response_models import (
    MultiSourceQueryResponse,
    MultiSourceInfo,
    SourceSearchResult,
    MultiSourceSearchResponse
)
from ..services.rag_service import get_rag_service
from ..services.db_vector_service import get_db_vector_service
from ..services.web_search_service import get_web_search_service
from ..services.ollama_service import get_ollama_service
from ..services.quality_service import get_quality_service
from ..config.database import get_db


class MultiSourceRAGService:
    """다중 데이터 소스를 통합한 RAG 서비스"""

    def __init__(self):
        self.search_strategies = {
            "balanced": self._balanced_search,
            "documents_first": self._documents_first_search,
            "comprehensive": self._comprehensive_search,
            "fast": self._fast_search
        }

    async def query(
        self,
        request: MultiSourceQueryRequest,
        db: AsyncSession
    ) -> MultiSourceQueryResponse:
        """다중 소스 질의 처리"""
        start_time = time.time()

        try:
            # 검색 전략 결정
            strategy = self._determine_search_strategy(request)
            logger.info(f"다중 소스 검색 시작: 전략={strategy}, 소스={request.data_sources}")

            # 소스별 검색 실행
            search_results = await self._execute_multi_source_search(request, db)

            # 결과 통합 및 답변 생성
            if request.combine_results:
                combined_response = await self._combine_and_generate_answer(
                    request, search_results, db
                )
                query_time = int((time.time() - start_time) * 1000)
                combined_response.query_time_ms = query_time
                return combined_response
            else:
                # 개별 결과 반환
                query_time = int((time.time() - start_time) * 1000)
                return MultiSourceSearchResponse(
                    question=request.question,
                    source_results=search_results,
                    total_search_time_ms=query_time,
                    successful_sources=sum(1 for r in search_results if r.status == "success"),
                    failed_sources=sum(1 for r in search_results if r.status == "failed")
                )

        except Exception as e:
            logger.error(f"다중 소스 질의 처리 실패: {e}")
            raise

    async def _execute_multi_source_search(
        self,
        request: MultiSourceQueryRequest,
        db: AsyncSession
    ) -> List[SourceSearchResult]:
        """소스별 병렬 검색 실행"""
        search_tasks = []

        # 각 데이터 소스별로 검색 태스크 생성
        for source in request.data_sources:
            if source == DataSource.DOCUMENTS:
                task = self._search_documents(request, db)
            elif source == DataSource.DATABASE:
                task = self._search_database(request, db)
            elif source == DataSource.WEB_SEARCH:
                task = self._search_web(request)
            else:
                continue

            search_tasks.append(task)

        # 병렬 실행
        if search_tasks:
            results = await asyncio.gather(*search_tasks, return_exceptions=True)

            # 예외 처리
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"소스 검색 실패 ({request.data_sources[i]}): {result}")
                    processed_results.append(SourceSearchResult(
                        source_type=request.data_sources[i],
                        results=[],
                        search_time_ms=0,
                        total_found=0,
                        status="failed",
                        error_message=str(result)
                    ))
                else:
                    processed_results.append(result)

            return processed_results
        else:
            return []

    async def _search_documents(
        self,
        request: MultiSourceQueryRequest,
        db: AsyncSession
    ) -> SourceSearchResult:
        """문서 검색"""
        start_time = time.time()

        try:
            # 기존 RAG 서비스 활용
            rag_service = await get_rag_service()

            # 기존 QueryRequest 형태로 변환
            from ..models.request_models import QueryRequest
            query_request = QueryRequest(
                question=request.question,
                user_role=request.user_role,
                document_filter=request.document_filter,
                top_k=request.top_k_per_source
            )

            # RAG 검색 실행
            rag_response = await rag_service.query(query_request)

            # MultiSourceInfo 형태로 변환
            multi_source_results = []
            for source in rag_response.sources:
                multi_source_results.append(MultiSourceInfo(
                    source_type=DataSource.DOCUMENTS,
                    source_id=source.document_id,
                    content=source.content_preview or "",
                    relevance_score=source.relevance_score,
                    document_name=source.document_name,
                    page_number=source.page_number,
                    section=source.section,
                    metadata={
                        "document_id": source.document_id,
                        "document_name": source.document_name
                    }
                ))

            search_time = int((time.time() - start_time) * 1000)

            return SourceSearchResult(
                source_type=DataSource.DOCUMENTS,
                results=multi_source_results,
                search_time_ms=search_time,
                total_found=len(multi_source_results),
                status="success"
            )

        except Exception as e:
            search_time = int((time.time() - start_time) * 1000)
            logger.error(f"문서 검색 실패: {e}")
            return SourceSearchResult(
                source_type=DataSource.DOCUMENTS,
                results=[],
                search_time_ms=search_time,
                total_found=0,
                status="failed",
                error_message=str(e)
            )

    async def _search_database(
        self,
        request: MultiSourceQueryRequest,
        db: AsyncSession
    ) -> SourceSearchResult:
        """데이터베이스 검색 (메타데이터 + 질의 기록)"""
        start_time = time.time()

        try:
            db_vector_service = await get_db_vector_service()

            # 문서 메타데이터 벡터화
            doc_metadata = await db_vector_service.vectorize_document_metadata(db)

            # 질의 기록 벡터화
            query_history = await db_vector_service.vectorize_query_history(db, limit=50)

            # 통합 검색
            all_vectorized_data = doc_metadata + query_history
            search_results = await db_vector_service.search_vectorized_data(
                request.question,
                all_vectorized_data,
                top_k=request.top_k_per_source
            )

            # MultiSourceInfo 형태로 변환
            multi_source_results = []
            for result in search_results:
                multi_source_results.append(MultiSourceInfo(
                    source_type=DataSource.DATABASE,
                    source_id=result["id"],
                    content=result["content"],
                    relevance_score=result["similarity"],
                    metadata=result["metadata"]
                ))

            search_time = int((time.time() - start_time) * 1000)

            return SourceSearchResult(
                source_type=DataSource.DATABASE,
                results=multi_source_results,
                search_time_ms=search_time,
                total_found=len(multi_source_results),
                status="success"
            )

        except Exception as e:
            search_time = int((time.time() - start_time) * 1000)
            logger.error(f"데이터베이스 검색 실패: {e}")
            return SourceSearchResult(
                source_type=DataSource.DATABASE,
                results=[],
                search_time_ms=search_time,
                total_found=0,
                status="failed",
                error_message=str(e)
            )

    async def _search_web(
        self,
        request: MultiSourceQueryRequest
    ) -> SourceSearchResult:
        """웹 검색"""
        start_time = time.time()

        try:
            if not request.enable_web_search:
                return SourceSearchResult(
                    source_type=DataSource.WEB_SEARCH,
                    results=[],
                    search_time_ms=0,
                    total_found=0,
                    status="disabled",
                    error_message="웹 검색이 비활성화되어 있습니다."
                )

            web_search_service = await get_web_search_service()

            # 검색 쿼리 결정 (사용자 지정 또는 원본 질문)
            search_query = request.web_search_query or request.question

            # 제조업 특화 검색 실행
            web_results = await web_search_service.search_manufacturing_specific(
                search_query,
                max_results=request.top_k_per_source
            )

            # 결과 검증
            validated_results = await web_search_service.validate_search_results(
                web_results,
                request.question
            )

            # MultiSourceInfo 형태로 변환
            multi_source_results = []
            for result in validated_results:
                multi_source_results.append(MultiSourceInfo(
                    source_type=DataSource.WEB_SEARCH,
                    source_id=result.get("url", ""),
                    content=result.get("content", ""),
                    relevance_score=result.get("relevance_score", 0.5),
                    url=result.get("url", ""),
                    web_source=result.get("source", ""),
                    metadata={
                        "title": result.get("title", ""),
                        "type": result.get("type", ""),
                        "source": result.get("source", "")
                    }
                ))

            search_time = int((time.time() - start_time) * 1000)

            return SourceSearchResult(
                source_type=DataSource.WEB_SEARCH,
                results=multi_source_results,
                search_time_ms=search_time,
                total_found=len(multi_source_results),
                status="success"
            )

        except Exception as e:
            search_time = int((time.time() - start_time) * 1000)
            logger.error(f"웹 검색 실패: {e}")
            return SourceSearchResult(
                source_type=DataSource.WEB_SEARCH,
                results=[],
                search_time_ms=search_time,
                total_found=0,
                status="failed",
                error_message=str(e)
            )

    async def _combine_and_generate_answer(
        self,
        request: MultiSourceQueryRequest,
        search_results: List[SourceSearchResult],
        db: AsyncSession
    ) -> MultiSourceQueryResponse:
        """검색 결과를 통합하여 최종 답변 생성"""

        # 모든 검색 결과 통합
        all_sources = []
        sources_by_type = {}

        for source_result in search_results:
            if source_result.status == "success":
                all_sources.extend(source_result.results)
                sources_by_type[source_result.source_type] = len(source_result.results)

        # 관련성 점수 기준으로 정렬
        all_sources.sort(key=lambda x: x.relevance_score, reverse=True)

        # 상위 결과만 선택 (최대 10개)
        top_sources = all_sources[:10]

        # 컨텍스트 구성
        context_parts = []
        for i, source in enumerate(top_sources, 1):
            source_label = f"[소스 {i}]"
            if source.source_type == DataSource.DOCUMENTS:
                source_label += f" (문서: {source.document_name})"
            elif source.source_type == DataSource.DATABASE:
                source_label += f" (DB: {source.metadata.get('source_type', 'unknown')})"
            elif source.source_type == DataSource.WEB_SEARCH:
                source_label += f" (웹: {source.web_source})"

            context_parts.append(f"{source_label}\n{source.content}")

        context = "\n\n".join(context_parts)

        # 역할별 프롬프트 생성
        role_prompts = {
            UserRole.ENGINEER: "기술적 세부사항과 사양에 중점을 두어 답변하세요.",
            UserRole.QUALITY: "품질 기준과 테스트 조건에 중점을 두어 답변하세요.",
            UserRole.SALES: "제품 특징과 장점에 중점을 두어 답변하세요.",
            UserRole.SUPPORT: "실용적인 해결책과 호환성에 중점을 두어 답변하세요."
        }

        role_instruction = role_prompts.get(request.user_role, role_prompts[UserRole.ENGINEER])

        prompt = f"""다음 질문에 대해 제공된 정보를 바탕으로 정확하고 유용한 답변을 제공하세요.

질문: {request.question}

역할 지침: {role_instruction}

참고 정보:
{context}

답변 지침:
1. 제공된 정보만을 바탕으로 답변하세요
2. 추측이나 불확실한 정보는 언급하지 마세요
3. 관련 소스를 적절히 인용하세요
4. 간결하고 명확하게 답변하세요

답변:"""

        # LLM으로 답변 생성
        ollama_service = await get_ollama_service()
        answer = await ollama_service.generate_response(prompt)

        # 품질 검증
        quality_service = await get_quality_service()
        source_contents = [source.content for source in top_sources]
        validation_result = quality_service.validate_answer(
            question=request.question,
            answer=answer,
            sources=[{"content": content} for content in source_contents],
            confidence=0.8
        )

        return MultiSourceQueryResponse(
            answer=answer,
            confidence=validation_result["confidence_adjusted"],
            sources=top_sources,
            query_time_ms=0,  # 상위에서 설정됨
            model_used=ollama_service.model,
            sources_by_type=sources_by_type,
            search_strategy="balanced",
            total_sources_searched=len(all_sources)
        )

    def _determine_search_strategy(self, request: MultiSourceQueryRequest) -> str:
        """검색 전략 결정"""
        # 간단한 휴리스틱 기반 전략 결정
        if len(request.data_sources) == 1:
            return "fast"
        elif DataSource.WEB_SEARCH in request.data_sources:
            return "comprehensive"
        elif request.top_k_per_source <= 3:
            return "fast"
        else:
            return "balanced"

    async def _balanced_search(self, request: MultiSourceQueryRequest, db: AsyncSession):
        """균형잡힌 검색 전략"""
        return await self._execute_multi_source_search(request, db)

    async def _documents_first_search(self, request: MultiSourceQueryRequest, db: AsyncSession):
        """문서 우선 검색 전략"""
        # 구현 필요 시 추가
        return await self._execute_multi_source_search(request, db)

    async def _comprehensive_search(self, request: MultiSourceQueryRequest, db: AsyncSession):
        """포괄적 검색 전략"""
        return await self._execute_multi_source_search(request, db)

    async def _fast_search(self, request: MultiSourceQueryRequest, db: AsyncSession):
        """빠른 검색 전략"""
        return await self._execute_multi_source_search(request, db)


# 싱글톤 인스턴스
_multi_source_rag_service = None


async def get_multi_source_rag_service() -> MultiSourceRAGService:
    """다중 소스 RAG 서비스 인스턴스 반환"""
    global _multi_source_rag_service
    if _multi_source_rag_service is None:
        _multi_source_rag_service = MultiSourceRAGService()
    return _multi_source_rag_service