import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from loguru import logger

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.config.settings import settings
from backend.config.database import init_database
from backend.api import upload, query, management, selftest, debug


# 로깅 설정
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level
)

if settings.log_file:
    log_dir = Path(settings.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        settings.log_file,
        rotation="1 day",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.log_level
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 시작 시 초기화
    logger.info("🚀 Manufacturing DataSheet RAG 시스템 시작")

    try:
        # 필수 의존성 확인
        try:
            import greenlet
            logger.info(f"✅ greenlet 확인됨: {greenlet.__version__}")
        except ImportError:
            logger.error("❌ greenlet 라이브러리가 없습니다. 'pip install greenlet>=3.0.0' 실행하세요.")
            raise

        # 데이터베이스 초기화
        await init_database()
        logger.info("✅ 데이터베이스 초기화 완료")

        # 필요한 디렉토리 생성
        Path(settings.upload_path).mkdir(parents=True, exist_ok=True)
        Path(settings.processed_path).mkdir(parents=True, exist_ok=True)
        Path(settings.vector_db_path).mkdir(parents=True, exist_ok=True)
        logger.info("✅ 디렉토리 구조 생성 완료")

        # Ollama 연결 확인
        try:
            from backend.services.ollama_service import get_ollama_service
            ollama_service = await get_ollama_service()
            is_available = await ollama_service.is_available()

            if is_available:
                logger.info("✅ Ollama 서버 연결 확인")

                # 모델 사용 가능성 확인
                model_available = await ollama_service.ensure_model_available()
                if model_available:
                    logger.info(f"✅ Ollama 모델 ({ollama_service.model}) 사용 가능")
                else:
                    logger.warning(f"⚠️ Ollama 모델 ({ollama_service.model}) 다운로드 필요")
            else:
                logger.warning("⚠️ Ollama 서버에 연결할 수 없습니다. 수동으로 확인해주세요.")
        except Exception as e:
            logger.error(f"❌ Ollama 연결 확인 실패: {e}")

        # 벡터 데이터베이스 초기화
        try:
            from backend.services.vector_service import get_vector_service
            vector_service = await get_vector_service()
            logger.info("✅ 벡터 검색 서비스 초기화 완료")

            # 임베딩 모델 미리 로드 (시간이 소요될 수 있음)
            logger.info("⏳ 임베딩 모델 사전 로딩 시작...")
            _ = vector_service.embedding_model
            logger.info("✅ 임베딩 모델 사전 로딩 완료")
        except Exception as e:
            logger.error(f"❌ 벡터 서비스 초기화 실패: {e}")

        logger.info("🎉 모든 서비스 초기화 완료")

        # 시작 메시지
        logger.info(f"🌟 {settings.app_name} v{settings.app_version}")
        logger.info(f"📖 API 문서: http://{settings.host}:{settings.port}/docs")
        logger.info(f"🔍 ReDoc: http://{settings.host}:{settings.port}/redoc")
        logger.info(f"💊 헬스체크: http://{settings.host}:{settings.port}/api/health")

    except Exception as e:
        logger.error(f"❌ 초기화 실패: {e}")
        raise

    yield

    # 종료 시 정리
    logger.info("🛑 시스템 종료 중...")

    try:
        # 임시 파일 정리
        from backend.services.pdf_service import get_pdf_service
        pdf_service = get_pdf_service()
        pdf_service.cleanup_temp_files(older_than_hours=0)  # 모든 임시 파일 정리
        logger.info("✅ 임시 파일 정리 완료")
    except Exception as e:
        logger.error(f"❌ 정리 작업 실패: {e}")

    logger.info("👋 시스템 종료 완료")


# FastAPI 앱 생성
app = FastAPI(
    title=settings.app_name,
    description="""
    제조업 현장에서 축적된 제품 Data Sheet(PDF)를 효율적으로 활용하기 위한 RAG 기반 검색 시스템

    ## 주요 기능

    * **PDF 문서 업로드**: 데이터시트를 업로드하고 자동으로 벡터화
    * **지능형 검색**: 자연어 질의를 통한 정확한 정보 검색
    * **역할별 최적화**: 엔지니어, 품질관리, 영업, 고객지원팀별 맞춤 답변
    * **출처 추적**: 답변과 함께 원문 페이지/섹션 정보 제공
    * **실시간 처리**: 빠른 응답 시간과 스트리밍 지원

    ## 사용자 역할

    * **Engineer**: 기술적 세부사항, 사양, 설계 파라미터 중심
    * **Quality**: 품질 기준, 한계치, 테스트 조건 중심
    * **Sales**: 제품 특징, 장점, 경쟁 우위 중심
    * **Support**: 문제해결, 호환성, 실용적 해결책 중심
    """,
    version=settings.app_version,
    lifespan=lifespan
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 구체적인 도메인 지정 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(upload.router)
app.include_router(query.router)
app.include_router(management.router)
app.include_router(selftest.router)
app.include_router(debug.router)

# 정적 파일 서빙 (프론트엔드)
frontend_path = project_root / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

    @app.get("/", response_class=RedirectResponse)
    async def redirect_to_frontend():
        return "/static/index.html"
else:
    @app.get("/")
    async def root():
        return {
            "message": "Manufacturing DataSheet RAG System",
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/api/health"
        }

# 헬스체크 엔드포인트 (로드밸런서용)
@app.get("/ping")
async def ping():
    return {"status": "ok"}

# 에러 핸들러
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {
        "error": "Not Found",
        "message": f"요청한 경로 '{request.url.path}'를 찾을 수 없습니다.",
        "docs": "/docs"
    }

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"내부 서버 오류: {exc}")
    return {
        "error": "Internal Server Error",
        "message": "서버에서 오류가 발생했습니다. 관리자에게 문의하세요."
    }

# 시작 메시지는 lifespan에서 처리됨

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )