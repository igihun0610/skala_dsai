#!/bin/bash

# RAG 시스템 서버 시작 스크립트
echo "🚀 Manufacturing DataSheet RAG 시스템 시작..."

# 프로젝트 디렉토리로 이동
cd "$(dirname "$0")"

# 가상환경 활성화 확인
if [ -d "dsai" ]; then
    echo "📦 가상환경 활성화 중..."
    source dsai/bin/activate

    # 의존성 확인
    echo "🔍 필수 의존성 확인..."
    python -c "import greenlet; print('✅ greenlet:', greenlet.__version__)" 2>/dev/null || {
        echo "❌ greenlet 설치 중..."
        pip install greenlet>=3.0.0
    }

    python -c "import sqlalchemy; print('✅ SQLAlchemy:', sqlalchemy.__version__)" 2>/dev/null || {
        echo "❌ SQLAlchemy 설치 중..."
        pip install -r requirements.txt
    }

    echo "✅ 의존성 확인 완료"
else
    echo "⚠️ 가상환경을 찾을 수 없습니다. 전역 Python 사용"
fi

# 환경변수 로드
if [ -f ".env" ]; then
    echo "🔧 환경변수 로드 중..."
    set -a
    source .env
    set +a
fi

# 데이터 디렉토리 생성
echo "📁 데이터 디렉토리 확인..."
mkdir -p data/uploads data/vectordb data/processed logs

echo "🌟 서버 시작..."
echo "📖 API 문서: http://localhost:8000/docs"
echo "🔍 ReDoc: http://localhost:8000/redoc"
echo ""

# 서버 시작 (프로덕션 모드 - 자동 재로드 비활성화)
echo "🔧 프로덕션 모드로 시작 (자동 재로드 비활성화)"
cd backend && python -c "
import uvicorn
from main import app
from backend.config.settings import settings

uvicorn.run(
    app,
    host=settings.host,
    port=settings.port,
    reload=False,  # 자동 재로드 비활성화
    log_level=settings.log_level.lower()
)
"