from typing import List
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from ..config.database import get_db
from ..models.request_models import (
    QueryRequest, BatchQueryRequest,
    MultiSourceQueryRequest, AdvancedMultiSourceRequest
)
from ..models.response_models import (
    QueryResponse, BatchQueryResponse,
    MultiSourceQueryResponse, MultiSourceSearchResponse
)
from ..services.rag_service import get_rag_service
from ..services.multi_source_rag_service import get_multi_source_rag_service

router = APIRouter(prefix="/api/query", tags=["질의응답"])


@router.post("", response_model=QueryResponse, summary="RAG 기반 질의응답")
async def query_documents(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    업로드된 문서들을 대상으로 질의응답을 수행합니다.

    사용자 역할별 최적화된 답변을 제공합니다:
    - engineer: 기술적 세부사항과 사양 중심
    - quality: 품질 기준과 한계치 중심
    - sales: 제품 특징과 장점 중심
    - support: 문제해결과 호환성 중심
    """
    try:
        if not request.question.strip():
            raise HTTPException(
                status_code=400,
                detail="질문을 입력해주세요."
            )

        logger.info(f"질의 요청 - 역할: {request.user_role}, 질문: {request.question[:100]}...")

        # RAG 서비스로 질의 처리
        rag_service = await get_rag_service()
        response = await rag_service.query(request)

        logger.info(f"질의 처리 완료 - 응답 시간: {response.query_time_ms}ms, 신뢰도: {response.confidence:.2f}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"질의응답 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"질의응답 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/batch", response_model=BatchQueryResponse, summary="배치 질의응답")
async def batch_query_documents(
    request: BatchQueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """여러 질문을 일괄 처리합니다."""
    try:
        if not request.queries:
            raise HTTPException(
                status_code=400,
                detail="처리할 질문이 없습니다."
            )

        logger.info(f"배치 질의 요청 - {len(request.queries)}개 질문")

        import time
        start_time = time.time()

        # RAG 서비스로 각 질의 처리
        rag_service = await get_rag_service()
        results = []

        for i, query_request in enumerate(request.queries):
            logger.info(f"배치 질의 처리 중: {i+1}/{len(request.queries)}")
            response = await rag_service.query(query_request)
            results.append(response)

        total_time = int((time.time() - start_time) * 1000)

        batch_response = BatchQueryResponse(
            results=results,
            total_time_ms=total_time
        )

        logger.info(f"배치 질의 완료 - 총 시간: {total_time}ms")

        return batch_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"배치 질의응답 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"배치 질의응답 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/stream", summary="스트리밍 질의응답")
async def stream_query_documents(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """실시간 스트리밍 방식으로 질의응답을 수행합니다."""
    try:
        if not request.question.strip():
            raise HTTPException(
                status_code=400,
                detail="질문을 입력해주세요."
            )

        logger.info(f"스트리밍 질의 요청: {request.question[:100]}...")

        from ..services.ollama_service import get_ollama_service
        from ..services.vector_service import get_vector_service

        # 컨텍스트 검색
        vector_service = await get_vector_service()
        search_results = await vector_service.search(
            query=request.question,
            top_k=request.top_k
        )

        if not search_results:
            async def no_results_generator():
                yield "data: 죄송합니다. 관련 정보를 찾을 수 없습니다.\n\n"

            return StreamingResponse(
                no_results_generator(),
                media_type="text/plain"
            )

        # 컨텍스트 구성
        context_parts = []
        for result in search_results:
            context_parts.append(result["content"])
        context = "\n".join(context_parts)

        # 스트리밍 응답 생성
        async def generate_streaming_response():
            try:
                ollama_service = await get_ollama_service()

                yield "data: [시작]\n\n"

                async for chunk in ollama_service.generate_streaming_response(
                    prompt=request.question,
                    context=context,
                    temperature=0.1
                ):
                    if chunk.strip():
                        yield f"data: {chunk}\n\n"

                yield "data: [종료]\n\n"

            except Exception as e:
                yield f"data: [오류] {str(e)}\n\n"

        return StreamingResponse(
            generate_streaming_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"스트리밍 질의응답 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"스트리밍 질의응답 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/popular", summary="인기 질문 조회")
async def get_popular_queries(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """자주 묻는 질문들을 조회합니다."""
    try:
        rag_service = await get_rag_service()
        popular_queries = await rag_service.get_popular_queries(limit)

        return {
            "popular_queries": popular_queries,
            "total": len(popular_queries)
        }

    except Exception as e:
        logger.error(f"인기 질문 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail="인기 질문을 조회하는 중 오류가 발생했습니다."
        )


@router.get("/statistics", summary="질의 통계 조회")
async def get_query_statistics(
    db: AsyncSession = Depends(get_db)
):
    """질의응답 시스템의 사용 통계를 조회합니다."""
    try:
        rag_service = await get_rag_service()
        stats = await rag_service.get_query_statistics()

        return stats

    except Exception as e:
        logger.error(f"질의 통계 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail="통계를 조회하는 중 오류가 발생했습니다."
        )


@router.post("/feedback/{query_id}", summary="답변 피드백 제공")
async def provide_feedback(
    query_id: str,
    rating: int,
    db: AsyncSession = Depends(get_db)
):
    """특정 질의응답에 대한 사용자 피드백을 저장합니다."""
    try:
        if not 1 <= rating <= 5:
            raise HTTPException(
                status_code=400,
                detail="평점은 1-5 사이의 값이어야 합니다."
            )

        from sqlalchemy import select, update
        from ..config.database import QueryLog

        # 쿼리 로그 존재 여부 확인
        result = await db.execute(
            select(QueryLog).where(QueryLog.id == query_id)
        )
        query_log = result.scalar_one_or_none()

        if not query_log:
            raise HTTPException(
                status_code=404,
                detail="해당 질의를 찾을 수 없습니다."
            )

        # 평점 업데이트
        await db.execute(
            update(QueryLog)
            .where(QueryLog.id == query_id)
            .values(rating=rating)
        )
        await db.commit()

        logger.info(f"피드백 저장 완료 - Query ID: {query_id}, Rating: {rating}")

        return {
            "message": "피드백이 성공적으로 저장되었습니다.",
            "query_id": query_id,
            "rating": rating
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"피드백 저장 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail="피드백 저장 중 오류가 발생했습니다."
        )


@router.post("/multi", response_model=MultiSourceQueryResponse, summary="다중 소스 통합 검색")
async def multi_source_query(
    request: MultiSourceQueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    여러 데이터 소스를 통합하여 질의응답을 수행합니다.

    지원 데이터 소스:
    - documents: 업로드된 PDF 문서
    - database: 문서 메타데이터 및 질의 기록
    - web_search: 실시간 웹 검색 (선택적)

    검색 결과를 통합하여 가장 관련성 높은 답변을 제공합니다.
    """
    try:
        if not request.question.strip():
            raise HTTPException(
                status_code=400,
                detail="질문을 입력해주세요."
            )

        logger.info(f"다중 소스 질의 요청 - 소스: {request.data_sources}, 질문: {request.question[:100]}...")

        # 다중 소스 RAG 서비스로 질의 처리
        multi_rag_service = await get_multi_source_rag_service()
        response = await multi_rag_service.query(request, db)

        logger.info(f"다중 소스 질의 완료 - 응답 시간: {response.query_time_ms}ms, 신뢰도: {response.confidence:.2f}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"다중 소스 질의응답 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"다중 소스 질의응답 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/multi/search", response_model=MultiSourceSearchResponse, summary="다중 소스 개별 검색")
async def multi_source_search(
    request: MultiSourceQueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    여러 데이터 소스에서 개별적으로 검색하여 결과를 분리하여 제공합니다.

    통합 답변 생성 없이 각 소스별 검색 결과만을 반환합니다.
    디버깅이나 소스별 결과 분석이 필요한 경우에 사용합니다.
    """
    try:
        if not request.question.strip():
            raise HTTPException(
                status_code=400,
                detail="질문을 입력해주세요."
            )

        # 결과 통합 비활성화
        search_request = request.model_copy()
        search_request.combine_results = False

        logger.info(f"다중 소스 개별 검색 요청 - 소스: {request.data_sources}")

        multi_rag_service = await get_multi_source_rag_service()
        response = await multi_rag_service.query(search_request, db)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"다중 소스 개별 검색 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"다중 소스 개별 검색 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/multi/advanced", response_model=MultiSourceQueryResponse, summary="고급 다중 소스 검색")
async def advanced_multi_source_query(
    request: AdvancedMultiSourceRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    소스별 가중치와 고급 설정을 적용한 다중 소스 검색을 수행합니다.

    추가 기능:
    - 소스별 가중치 조정
    - 최소 관련성 임계값 설정
    - 제조업 특화 검색 옵션
    - 웹 검색 엔진 선택
    """
    try:
        if not request.question.strip():
            raise HTTPException(
                status_code=400,
                detail="질문을 입력해주세요."
            )

        # 기본 MultiSourceQueryRequest로 변환
        basic_request = MultiSourceQueryRequest(
            question=request.question,
            user_role=request.user_role,
            data_sources=request.data_sources,
            document_filter=request.document_filter,
            top_k_per_source=request.top_k_per_source,
            enable_web_search=request.enable_web_search,
            combine_results=True
        )

        logger.info(f"고급 다중 소스 질의 요청 - 제조업 특화: {request.manufacturing_focus}")

        multi_rag_service = await get_multi_source_rag_service()
        response = await multi_rag_service.query(basic_request, db)

        # 가중치가 설정된 경우 결과 조정
        if request.source_weights:
            response = _apply_source_weights(response, request.source_weights)

        # 최소 관련성 임계값 적용
        if request.min_relevance_threshold > 0:
            response.sources = [
                source for source in response.sources
                if source.relevance_score >= request.min_relevance_threshold
            ]

        logger.info(f"고급 다중 소스 질의 완료 - 최종 소스 수: {len(response.sources)}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"고급 다중 소스 질의응답 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"고급 다중 소스 질의응답 처리 중 오류가 발생했습니다: {str(e)}"
        )


def _apply_source_weights(response: MultiSourceQueryResponse, weights) -> MultiSourceQueryResponse:
    """소스별 가중치를 적용하여 관련성 점수를 조정"""
    from ..models.request_models import DataSource

    weight_map = {
        DataSource.DOCUMENTS: weights.documents,
        DataSource.DATABASE: weights.database,
        DataSource.WEB_SEARCH: weights.web_search
    }

    # 각 소스의 관련성 점수에 가중치 적용
    for source in response.sources:
        if source.source_type in weight_map:
            source.relevance_score *= weight_map[source.source_type]

    # 조정된 점수로 재정렬
    response.sources.sort(key=lambda x: x.relevance_score, reverse=True)

    return response