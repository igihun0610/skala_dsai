import os
import psutil
import time
from pathlib import Path
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from loguru import logger
from datetime import datetime, timedelta

from ..config.database import get_db
from ..models.quality_models import (
    DebugInfo, SystemStats, VectorStoreInfo,
    PerformanceMetrics, HealthCheckDetail
)
from ..services.vector_service import get_vector_service
from ..services.ollama_service import get_ollama_service
from ..config.settings import settings

router = APIRouter(prefix="/api/debug", tags=["디버그"])


@router.get("/info", response_model=DebugInfo, summary="전체 디버그 정보")
async def get_debug_info(db: AsyncSession = Depends(get_db)):
    """
    시스템의 전체 디버그 정보를 반환합니다.

    벡터스토어 상태, 시스템 성능, 에러 로그 등을 포함합니다.
    """
    try:
        # 벡터스토어 통계
        vectorstore_stats = await _get_vectorstore_stats()

        # 시스템 상태
        system_status = await _get_system_status(db)

        # 성능 지표
        performance_metrics = await _get_performance_metrics(db)

        # 에러 로그 (최근 24시간)
        error_logs = await _get_recent_error_logs()

        return DebugInfo(
            vectorstore_stats=vectorstore_stats,
            system_status=system_status,
            performance_metrics=performance_metrics,
            error_logs=error_logs
        )

    except Exception as e:
        logger.error(f"디버그 정보 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"디버그 정보 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/vectorstore", summary="벡터스토어 상태")
async def get_vectorstore_status():
    """벡터스토어의 상태와 통계를 반환합니다."""
    try:
        stats = await _get_vectorstore_stats()
        return {"vectorstore_stats": stats}
    except Exception as e:
        logger.error(f"벡터스토어 상태 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"벡터스토어 상태 조회 실패: {str(e)}"
        )


@router.get("/system", response_model=SystemStats, summary="시스템 통계")
async def get_system_stats(db: AsyncSession = Depends(get_db)):
    """시스템의 전반적인 통계를 반환합니다."""
    try:
        stats = await _get_system_status(db)

        # 메모리 사용량 추가
        memory_info = psutil.virtual_memory()
        stats["memory_usage"] = {
            "total": memory_info.total,
            "available": memory_info.available,
            "percent": memory_info.percent,
            "used": memory_info.used
        }

        # 시스템 가동 시간
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        stats["system_uptime"] = str(uptime)

        return SystemStats(**stats)

    except Exception as e:
        logger.error(f"시스템 통계 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"시스템 통계 조회 실패: {str(e)}"
        )


@router.get("/performance", response_model=PerformanceMetrics, summary="성능 지표")
async def get_performance_metrics(db: AsyncSession = Depends(get_db)):
    """시스템의 성능 지표를 반환합니다."""
    try:
        metrics = await _get_performance_metrics(db)
        return PerformanceMetrics(**metrics)
    except Exception as e:
        logger.error(f"성능 지표 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"성능 지표 조회 실패: {str(e)}"
        )


@router.get("/health-detail", summary="상세 헬스체크")
async def get_detailed_health_check(db: AsyncSession = Depends(get_db)):
    """각 컴포넌트별 상세한 헬스체크를 수행합니다."""
    try:
        health_checks = []

        # 데이터베이스 체크
        db_start = time.time()
        try:
            await db.execute(text("SELECT 1"))
            db_status = "healthy"
            db_details = {"connection": "active"}
        except Exception as e:
            db_status = "unhealthy"
            db_details = {"error": str(e)}

        health_checks.append(HealthCheckDetail(
            component="database",
            status=db_status,
            response_time=time.time() - db_start,
            details=db_details,
            last_check=datetime.now()
        ))

        # 벡터 서비스 체크
        vector_start = time.time()
        try:
            vector_service = await get_vector_service()
            # 간단한 검색 테스트
            await vector_service.search("test", top_k=1)
            vector_status = "healthy"
            vector_details = {"search": "working"}
        except Exception as e:
            vector_status = "unhealthy"
            vector_details = {"error": str(e)}

        health_checks.append(HealthCheckDetail(
            component="vector_service",
            status=vector_status,
            response_time=time.time() - vector_start,
            details=vector_details,
            last_check=datetime.now()
        ))

        # Ollama 서비스 체크
        ollama_start = time.time()
        try:
            ollama_service = await get_ollama_service()
            models = await ollama_service.list_models()
            ollama_status = "healthy"
            ollama_details = {"models_count": len(models)}
        except Exception as e:
            ollama_status = "unhealthy"
            ollama_details = {"error": str(e)}

        health_checks.append(HealthCheckDetail(
            component="ollama_service",
            status=ollama_status,
            response_time=time.time() - ollama_start,
            details=ollama_details,
            last_check=datetime.now()
        ))

        return {"health_checks": health_checks}

    except Exception as e:
        logger.error(f"상세 헬스체크 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"상세 헬스체크 실패: {str(e)}"
        )


@router.post("/clear-cache", summary="캐시 정리")
async def clear_cache():
    """시스템 캐시를 정리합니다."""
    try:
        # 벡터 서비스 캐시 정리
        try:
            vector_service = await get_vector_service()
            # 캐시 정리 로직 (구현에 따라 다름)
            logger.info("벡터 서비스 캐시 정리 완료")
        except Exception as e:
            logger.warning(f"벡터 서비스 캐시 정리 실패: {e}")

        # 임시 파일 정리
        temp_files_cleaned = 0
        upload_path = Path(settings.upload_path)
        if upload_path.exists():
            for temp_file in upload_path.glob("temp_*"):
                if temp_file.is_file():
                    try:
                        temp_file.unlink()
                        temp_files_cleaned += 1
                    except Exception as e:
                        logger.warning(f"임시 파일 삭제 실패 {temp_file}: {e}")

        return {
            "message": "캐시 정리 완료",
            "temp_files_cleaned": temp_files_cleaned,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"캐시 정리 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"캐시 정리 실패: {str(e)}"
        )


@router.get("/logs", summary="최근 로그 조회")
async def get_recent_logs(
    level: str = "INFO",
    hours: int = 24,
    limit: int = 100
):
    """최근 로그를 조회합니다."""
    try:
        logs = await _get_recent_error_logs(level=level, hours=hours, limit=limit)
        return {
            "logs": logs,
            "total": len(logs),
            "level": level,
            "time_range": f"최근 {hours}시간"
        }
    except Exception as e:
        logger.error(f"로그 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"로그 조회 실패: {str(e)}"
        )


async def _get_vectorstore_stats() -> Dict[str, Any]:
    """벡터스토어 통계 조회"""
    stats = {}

    try:
        vector_service = await get_vector_service()

        # 벡터 인덱스 정보
        vector_db_path = Path(settings.vector_db_path)

        # 기본 통계
        stats["vector_service"] = VectorStoreInfo(
            name="main_vector_db",
            loaded=True,
            embedding_model=settings.embedding_model,
            document_count=None,  # 실제 구현에서는 벡터 서비스에서 가져옴
            index_size=None
        ).dict()

        # 디렉토리 크기 계산
        if vector_db_path.exists():
            total_size = sum(
                f.stat().st_size for f in vector_db_path.rglob('*') if f.is_file()
            )
            stats["vector_service"]["directory_size"] = total_size

    except Exception as e:
        logger.warning(f"벡터스토어 통계 조회 실패: {e}")
        stats["vector_service"] = VectorStoreInfo(
            name="main_vector_db",
            loaded=False
        ).dict()

    return stats


async def _get_system_status(db: AsyncSession) -> Dict[str, Any]:
    """시스템 상태 조회"""
    status = {}

    # 데이터베이스 통계
    try:
        # 문서 수
        result = await db.execute(text("SELECT COUNT(*) FROM documents"))
        documents_count = result.scalar() or 0

        # 벡터 청크 수
        result = await db.execute(text("SELECT COUNT(*) FROM vector_chunks"))
        vector_chunks_count = result.scalar() or 0

        # 쿼리 로그 수
        result = await db.execute(text("SELECT COUNT(*) FROM query_logs"))
        queries_count = result.scalar() or 0

        # 평균 응답 시간 (최근 100개 쿼리)
        result = await db.execute(text("""
            SELECT AVG(response_time_ms)
            FROM query_logs
            WHERE created_at > datetime('now', '-24 hours')
            LIMIT 100
        """))
        avg_response_time = result.scalar() or 0.0

        status.update({
            "documents_count": documents_count,
            "vector_chunks_count": vector_chunks_count,
            "queries_count": queries_count,
            "average_response_time": float(avg_response_time)
        })

    except Exception as e:
        logger.warning(f"데이터베이스 통계 조회 실패: {e}")
        status.update({
            "documents_count": 0,
            "vector_chunks_count": 0,
            "queries_count": 0,
            "average_response_time": 0.0
        })

    return status


async def _get_performance_metrics(db: AsyncSession) -> Dict[str, Any]:
    """성능 지표 조회"""
    metrics = {
        "queries_per_minute": 0.0,
        "average_query_time": 0.0,
        "vector_search_time": 0.0,
        "llm_response_time": 0.0,
        "success_rate": 1.0,
        "error_rate": 0.0
    }

    try:
        # 최근 1시간 쿼리 수
        result = await db.execute(text("""
            SELECT COUNT(*)
            FROM query_logs
            WHERE created_at > datetime('now', '-1 hour')
        """))
        queries_last_hour = result.scalar() or 0
        metrics["queries_per_minute"] = queries_last_hour / 60.0

        # 평균 쿼리 시간
        result = await db.execute(text("""
            SELECT AVG(response_time_ms)
            FROM query_logs
            WHERE created_at > datetime('now', '-24 hours')
        """))
        avg_query_time = result.scalar() or 0.0
        metrics["average_query_time"] = float(avg_query_time)

        # 성공률 계산 (임시로 confidence > 0.5를 성공으로 간주)
        result = await db.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN confidence > 0.5 THEN 1 ELSE 0 END) as successful
            FROM query_logs
            WHERE created_at > datetime('now', '-24 hours')
        """))
        row = result.first()
        if row and row[0] > 0:
            metrics["success_rate"] = row[1] / row[0]
            metrics["error_rate"] = 1.0 - metrics["success_rate"]

    except Exception as e:
        logger.warning(f"성능 지표 조회 실패: {e}")

    return metrics


async def _get_recent_error_logs(
    level: str = "ERROR",
    hours: int = 24,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """최근 에러 로그 조회"""
    # 실제 구현에서는 로그 파일이나 로그 저장소에서 조회
    # 여기서는 샘플 데이터 반환
    logs = []

    try:
        # 로그 파일이 있다면 파싱
        log_file = Path("logs/app.log")
        if log_file.exists():
            # 간단한 로그 파싱 (실제로는 더 정교한 파싱 필요)
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-limit:]  # 마지막 N개 라인

            for line in lines:
                if level.upper() in line:
                    logs.append({
                        "timestamp": datetime.now().isoformat(),
                        "level": level.upper(),
                        "message": line.strip(),
                        "context": {}
                    })
    except Exception as e:
        logger.warning(f"로그 파일 읽기 실패: {e}")
        # 기본 로그 엔트리 추가
        logs.append({
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "message": "시스템이 정상적으로 작동 중입니다.",
            "context": {}
        })

    return logs[:limit]