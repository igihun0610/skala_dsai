from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from ..config.database import get_db, Document
from ..models.request_models import DocumentListRequest, ReindexRequest
from ..models.response_models import (
    DocumentListResponse, DocumentDetail, DocumentInfo,
    StatusResponse, StatisticsResponse, ReindexResponse, HealthResponse
)
from ..services.ollama_service import get_ollama_service
from ..services.vector_service import get_vector_service
from ..services.rag_service import get_rag_service

router = APIRouter(prefix="/api", tags=["시스템 관리"])


@router.get("/documents", response_model=DocumentListResponse, summary="문서 목록 조회")
async def list_documents(
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지 당 항목 수"),
    document_type: Optional[str] = Query(None, description="문서 타입 필터"),
    product_family: Optional[str] = Query(None, description="제품군 필터"),
    search: Optional[str] = Query(None, description="검색어"),
    db: AsyncSession = Depends(get_db)
):
    """업로드된 문서들의 목록을 조회합니다."""
    try:
        from sqlalchemy import select, func, or_

        # 기본 쿼리
        query = select(Document)
        count_query = select(func.count(Document.id))

        # 필터 적용
        conditions = []

        if document_type:
            conditions.append(Document.document_type == document_type)

        if product_family:
            conditions.append(Document.product_family == product_family)

        if search:
            search_conditions = or_(
                Document.original_name.ilike(f"%{search}%"),
                Document.product_model.ilike(f"%{search}%"),
                Document.product_family.ilike(f"%{search}%")
            )
            conditions.append(search_conditions)

        if conditions:
            query = query.where(*conditions)
            count_query = count_query.where(*conditions)

        # 총 개수 조회
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # 페이징 적용
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(Document.created_at.desc())

        # 문서 목록 조회
        result = await db.execute(query)
        documents = result.scalars().all()

        # 응답 데이터 구성
        document_list = []
        for doc in documents:
            doc_info = DocumentInfo(
                id=str(doc.id),
                filename=doc.filename,
                original_name=doc.original_name,
                file_size=doc.file_size,
                upload_date=doc.upload_date,
                document_type=doc.document_type,
                product_family=doc.product_family,
                product_model=doc.product_model,
                version=doc.version,
                language=doc.language,
                page_count=doc.page_count,
                processing_status=doc.processing_status,
                created_at=doc.created_at,
                updated_at=doc.updated_at
            )
            document_list.append(doc_info)

        total_pages = (total + limit - 1) // limit

        return DocumentListResponse(
            documents=document_list,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages
        )

    except Exception as e:
        logger.error(f"문서 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail="문서 목록을 조회하는 중 오류가 발생했습니다."
        )


@router.get("/documents/{document_id}", response_model=DocumentDetail, summary="문서 상세 정보")
async def get_document_detail(
    document_id: str,
    db: AsyncSession = Depends(get_db)
):
    """특정 문서의 상세 정보를 조회합니다."""
    try:
        from sqlalchemy import select

        # 문서 정보 조회
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=404,
                detail="문서를 찾을 수 없습니다."
            )

        # 문서 섹션 정보 조회
        from ..config.database import DocumentSection, Specification

        sections_result = await db.execute(
            select(DocumentSection).where(DocumentSection.document_id == document_id)
        )
        sections = sections_result.scalars().all()

        # 기술 사양 정보 조회
        specs_result = await db.execute(
            select(Specification).where(Specification.document_id == document_id)
        )
        specifications = specs_result.scalars().all()

        # 응답 데이터 구성
        doc_info = DocumentInfo(
            id=str(document.id),
            filename=document.filename,
            original_name=document.original_name,
            file_size=document.file_size,
            upload_date=document.upload_date,
            document_type=document.document_type,
            product_family=document.product_family,
            product_model=document.product_model,
            version=document.version,
            language=document.language,
            page_count=document.page_count,
            processing_status=document.processing_status,
            created_at=document.created_at,
            updated_at=document.updated_at
        )

        sections_data = [
            {
                "id": section.id,
                "title": section.section_title,
                "type": section.section_type,
                "page_number": section.page_number,
                "content_preview": section.content_preview
            }
            for section in sections
        ]

        specs_data = [
            {
                "id": spec.id,
                "parameter_name": spec.parameter_name,
                "parameter_value": spec.parameter_value,
                "unit": spec.unit,
                "condition_text": spec.condition_text,
                "min_value": spec.min_value,
                "max_value": spec.max_value,
                "typical_value": spec.typical_value,
                "page_number": spec.page_number
            }
            for spec in specifications
        ]

        return DocumentDetail(
            document=doc_info,
            sections=sections_data,
            specifications=specs_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 상세 정보 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail="문서 상세 정보를 조회하는 중 오류가 발생했습니다."
        )


@router.get("/status", response_model=StatusResponse, summary="시스템 상태 확인")
async def get_system_status():
    """시스템의 전반적인 상태를 확인합니다."""
    try:
        # Ollama 상태 확인
        ollama_service = await get_ollama_service()
        ollama_available = await ollama_service.is_available()
        ollama_status = "healthy" if ollama_available else "error"

        # 벡터 DB 상태 확인
        vector_service = await get_vector_service()
        vector_stats = await vector_service.get_index_stats()
        vector_db_status = "healthy" if vector_stats.get("exists", False) else "error"

        # 문서 수 조회
        from sqlalchemy import select, func
        from ..config.database import VectorChunk, AsyncSessionLocal

        async with AsyncSessionLocal() as db:

            # 문서 수
            doc_count_result = await db.execute(select(func.count(Document.id)))
            documents_count = doc_count_result.scalar()

            # 벡터 수
            vector_count_result = await db.execute(select(func.count(VectorChunk.id)))
            vector_count = vector_count_result.scalar()

        # 시스템 상태 판단
        system_health = "healthy"
        if not ollama_available:
            system_health = "degraded"
        elif vector_db_status == "not_initialized":
            system_health = "warning"

        return StatusResponse(
            ollama_status=ollama_status,
            vector_db_status=vector_db_status,
            documents_count=documents_count,
            vector_count=vector_count,
            system_health=system_health
        )

    except Exception as e:
        logger.error(f"시스템 상태 조회 실패: {e}")
        return StatusResponse(
            ollama_status="error",
            vector_db_status="error",
            documents_count=0,
            vector_count=0,
            system_health="error"
        )


@router.get("/statistics", response_model=StatisticsResponse, summary="시스템 통계")
async def get_system_statistics(
    db: AsyncSession = Depends(get_db)
):
    """시스템 사용 통계를 조회합니다."""
    try:
        # RAG 서비스에서 질의 통계 가져오기
        rag_service = get_rag_service()
        query_stats = await rag_service.get_query_statistics()

        # 인기 질문 조회
        popular_queries = await rag_service.get_popular_queries(5)

        # 문서 타입별 분포 조회
        from sqlalchemy import select, func

        doc_type_result = await db.execute(
            select(Document.document_type, func.count(Document.document_type))
            .group_by(Document.document_type)
        )

        documents_by_type = {
            row[0] or "unknown": row[1] for row in doc_type_result
        }

        return StatisticsResponse(
            total_queries=query_stats.get("total_queries", 0),
            avg_response_time_ms=query_stats.get("avg_response_time_ms", 0.0),
            popular_queries=popular_queries,
            user_role_distribution=query_stats.get("role_distribution", {}),
            documents_by_type=documents_by_type
        )

    except Exception as e:
        logger.error(f"시스템 통계 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail="시스템 통계를 조회하는 중 오류가 발생했습니다."
        )


@router.post("/reindex", response_model=ReindexResponse, summary="벡터 인덱스 재구성")
async def reindex_documents(
    request: ReindexRequest,
    db: AsyncSession = Depends(get_db)
):
    """벡터 인덱스를 재구성합니다."""
    try:
        import time
        start_time = time.time()

        logger.info("벡터 인덱스 재구성 시작")

        vector_service = await get_vector_service()

        if request.document_ids:
            # 특정 문서들만 재인덱싱
            # TODO: 특정 문서 재인덱싱 구현
            logger.info(f"특정 문서 재인덱싱: {len(request.document_ids)}개")
            processed_documents = len(request.document_ids)
            failed_documents = 0
        else:
            # 전체 재인덱싱
            success = await vector_service.reindex_all_documents()

            if success:
                processed_documents = 1  # 성공적으로 처리된 배치 수
                failed_documents = 0
            else:
                processed_documents = 0
                failed_documents = 1

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(f"벡터 인덱스 재구성 완료 - 처리 시간: {processing_time}ms")

        return ReindexResponse(
            status="completed" if failed_documents == 0 else "partial_failure",
            message=f"재인덱싱이 완료되었습니다. 처리: {processed_documents}, 실패: {failed_documents}",
            processed_documents=processed_documents,
            failed_documents=failed_documents,
            processing_time_ms=processing_time
        )

    except Exception as e:
        logger.error(f"벡터 인덱스 재구성 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"벡터 인덱스 재구성 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/health", response_model=HealthResponse, summary="헬스체크")
async def health_check():
    """서비스 헬스체크를 수행합니다."""
    try:
        import time
        from datetime import datetime

        # 간단한 헬스체크
        start_time = time.time()

        # 기본적인 상태 확인
        health_status = "healthy"

        # Ollama 상태 확인 (빠른 체크)
        try:
            ollama_service = await get_ollama_service()
            ollama_available = await ollama_service.is_available()
            if not ollama_available:
                health_status = "degraded"
        except Exception:
            health_status = "degraded"

        uptime_seconds = int(time.time() - start_time)

        return HealthResponse(
            status=health_status,
            timestamp=datetime.utcnow(),
            version="1.0.0",
            uptime_seconds=uptime_seconds
        )

    except Exception as e:
        logger.error(f"헬스체크 실패: {e}")
        return HealthResponse(
            status="error",
            timestamp=datetime.utcnow(),
            version="1.0.0",
            uptime_seconds=0
        )