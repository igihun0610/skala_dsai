# 제조업 Data Sheet RAG 시스템

SK Hynix 등 제조업 현장에서 축적된 제품 Data Sheet(PDF)를 효율적으로 활용하기 위한 RAG 기반 지능형 검색 시스템입니다.

## 🎯 주요 특징

- **PDF 데이터시트 자동 처리**: 복잡한 기술 문서를 자동으로 파싱하고 구조화
- **지능형 질의응답**: 자연어 질문으로 정확한 기술 정보 검색
- **역할별 맞춤 답변**: 엔지니어, 품질관리, 영업, 고객지원팀별 특화 답변
- **정확한 출처 추적**: 답변과 함께 원문 페이지/섹션 정보 제공
- **로컬 LLM 활용**: Ollama를 통한 보안이 강화된 온프레미스 운영

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   웹 인터페이스   │    │   FastAPI 서버   │    │   Ollama LLM    │
│   (React/HTML)  │◄──►│      RAG         │◄──►│   (llama3 등)   │
└─────────────────┘    │   파이프라인      │    └─────────────────┘
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  벡터 데이터베이스  │
                       │     (FAISS)     │
                       │   + 메타데이터    │
                       │   (SQLite)      │
                       └─────────────────┘
```

## 🛠️ 기술 스택

### 백엔드
- **FastAPI**: 고성능 비동기 웹 프레임워크
- **Ollama**: 로컬 LLM 서버 (llama3, codellama, mistral 등)
- **LangChain**: RAG 파이프라인 및 문서 처리
- **FAISS**: 고성능 벡터 유사도 검색
- **sentence-transformers**: 다국어 임베딩 (BGE-M3)
- **SQLite**: 메타데이터 및 로그 저장

### 프론트엔드 (Phase 3)
- **React/HTML**: 사용자 인터페이스
- **Material-UI**: UI 컴포넌트
- **Axios**: API 통신

## 📋 설치 및 실행

### 1. 사전 요구사항
- Python 3.8+
- Git

### 2. 프로젝트 클론
```bash
git clone <repository-url>
cd cs_rag_project
```

### 3. Python 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. Ollama 설정 (자동 설치)
```bash
cd scripts
./setup_ollama.sh
```

또는 수동 설치:
```bash
# Ollama 설치
curl -fsSL https://ollama.com/install.sh | sh

# Ollama 서버 시작
ollama serve &

# 모델 다운로드 (선택)
ollama pull llama3        # 기본 모델 (추천)
ollama pull codellama     # 코드 특화 모델
ollama pull mistral       # 빠른 응답 모델
```

### 5. 환경 설정
```bash
cp .env.example .env
# 필요시 .env 파일 수정
```

### 6. 데이터 디렉토리 생성
```bash
mkdir -p data/{uploads,vectordb,processed} logs
```

### 7. 서버 실행
```bash
python backend/main.py
```

또는 uvicorn 직접 실행:
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## 🚀 사용법

### API 문서 접근
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 기본 워크플로우

#### 1. 문서 업로드
```bash
curl -X POST "http://localhost:8000/api/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@datasheet.pdf" \
  -F "document_type=datasheet" \
  -F "product_family=DDR5" \
  -F "product_model=RDIMM"
```

#### 2. 질의응답
```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "DDR5의 동작 전압은?",
    "user_role": "engineer",
    "top_k": 5
  }'
```

## 👥 사용자 역할별 기능

### 🔧 Engineer (엔지니어)
- 기술적 세부사항과 사양 중심
- 정확한 수치, 파라미터, 설계 조건
- 전기적/기계적 특성 정보

### 🔍 Quality (품질관리)
- 품질 기준, 한계치, 허용 오차
- 테스트 조건 및 검증 방법
- 규격 준수 및 인증 정보

### 💼 Sales (영업팀)
- 제품 특징과 경쟁 우위
- 고객 가치 중심 설명
- 활용 사례 및 시장 포지션

### 🛠️ Support (고객지원)
- 문제해결 및 트러블슈팅
- 호환성 및 설치 가이드
- 실용적 해결책 및 대안

## 📊 API 엔드포인트

### 파일 관리
- `POST /api/upload` - PDF 파일 업로드 및 처리
- `GET /api/upload/status/{document_id}` - 문서 처리 상태 확인
- `DELETE /api/upload/{document_id}` - 문서 삭제

### 질의응답
- `POST /api/query` - 단일 질의응답
- `POST /api/query/batch` - 배치 질의응답
- `POST /api/query/stream` - 스트리밍 질의응답
- `GET /api/query/popular` - 인기 질문 조회

### 시스템 관리
- `GET /api/documents` - 문서 목록 조회
- `GET /api/documents/{document_id}` - 문서 상세 정보
- `GET /api/status` - 시스템 상태 확인
- `GET /api/statistics` - 사용 통계 조회
- `POST /api/reindex` - 벡터 인덱스 재구성
- `GET /api/health` - 헬스체크

## 🎛️ 환경 설정

주요 환경변수 (`,.env` 파일):

```bash
# 서버 설정
HOST=0.0.0.0
PORT=8000

# Ollama 설정
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3
OLLAMA_TIMEOUT=120

# 벡터 DB 설정
EMBEDDING_MODEL=BAAI/bge-m3
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# 파일 설정
MAX_FILE_SIZE=104857600  # 100MB
UPLOAD_PATH=./data/uploads

# RAG 설정
TOP_K_RETRIEVAL=5
TEMPERATURE=0.1
```

## 🧪 테스트

### 헬스체크
```bash
curl http://localhost:8000/api/health
```

### 시스템 상태 확인
```bash
curl http://localhost:8000/api/status
```

### 샘플 질의 테스트
```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "시스템 테스트",
    "user_role": "engineer",
    "top_k": 3
  }'
```

## 🔧 개발 및 확장

### 프로젝트 구조
```
cs_rag_project/
├── backend/
│   ├── main.py              # FastAPI 메인 애플리케이션
│   ├── models/              # Pydantic 모델
│   ├── services/            # 비즈니스 로직 서비스
│   ├── api/                 # API 라우터
│   ├── config/              # 설정 및 데이터베이스
│   └── utils/               # 유틸리티 함수
├── data/                    # 데이터 저장소
├── scripts/                 # 설치 및 관리 스크립트
├── docs/                    # 문서화
└── requirements.txt         # Python 의존성
```

### 로컬 개발 모드
```bash
# 개발 모드로 실행 (자동 재로드)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 로그 레벨 조정
LOG_LEVEL=DEBUG python backend/main.py
```

## 📈 성능 최적화

### 벡터 검색 최적화
- FAISS IVF 인덱스 사용으로 검색 속도 향상
- 임베딩 캐싱으로 중복 계산 방지
- 적응형 청크 크기 조절

### 메모리 관리
- 지연 로딩을 통한 메모리 사용량 최적화
- 배치 처리로 대용량 문서 효율적 처리
- 임시 파일 자동 정리

## ⚠️ 주의사항

### 보안
- 민감한 기술 문서는 적절한 접근 권한 설정
- 프로덕션 환경에서는 CORS 설정 제한
- API 키 및 인증 시스템 추가 권장

### 성능
- 대용량 PDF (>50MB)는 처리 시간이 길어질 수 있음
- 동시 사용자 수에 따른 Ollama 모델 리소스 관리 필요
- 벡터 DB 크기에 따른 메모리 요구사항 고려

## 🐛 트러블슈팅

### 일반적인 문제들

1. **Ollama 연결 실패**
   ```bash
   # Ollama 서비스 상태 확인
   ps aux | grep ollama

   # Ollama 재시작
   pkill -f "ollama serve"
   ollama serve &
   ```

2. **모델 다운로드 실패**
   ```bash
   # 네트워크 상태 확인 후 재시도
   ollama pull llama3
   ```

3. **PDF 처리 실패**
   - 스캔된 PDF는 OCR 처리 후 업로드
   - 파일 크기 제한 확인 (기본 100MB)
   - PDF 파일 손상 여부 확인

4. **메모리 부족**
   - 청크 크기 줄이기 (CHUNK_SIZE=500)
   - 더 작은 임베딩 모델 사용
   - 시스템 메모리 증설

### 로그 확인
```bash
# 애플리케이션 로그
tail -f logs/app.log

# Ollama 로그 (백그라운드 실행 시)
tail -f /tmp/ollama.log
```

## 🗺️ 로드맵

### Phase 1: 기반 시스템 (완료)
- [x] FastAPI 프로젝트 구조
- [x] Ollama 연동
- [x] PDF 파싱 및 청킹
- [x] FAISS 벡터 DB
- [x] 기본 RAG 파이프라인
- [x] SQLite 메타데이터 관리

### Phase 2: 제조업 특화 기능 (예정)
- [ ] 데이터시트 구조화 파싱
- [ ] 기술 사양 추출 알고리즘
- [ ] 테이블 및 차트 처리
- [ ] 사용자 역할별 필터링 강화

### Phase 3: 프론트엔드 (예정)
- [ ] React 웹 인터페이스
- [ ] 파일 업로드 UI
- [ ] 채팅 인터페이스
- [ ] 검색 결과 시각화

### Phase 4: 운영 최적화 (예정)
- [ ] Docker 컨테이너화
- [ ] 성능 모니터링
- [ ] 자동화된 테스트
- [ ] CI/CD 파이프라인

## 📞 지원

- **이슈 리포팅**: GitHub Issues
- **문의사항**: 프로젝트 담당자에게 연락
- **기여하기**: Pull Request 환영

## 📄 라이선스

이 프로젝트는 교육 및 연구 목적으로 개발되었습니다.