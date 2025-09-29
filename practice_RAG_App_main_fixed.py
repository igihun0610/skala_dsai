#### 다음 실습 코드는 학습 목적으로만 사용 바랍니다. 문의 : audit@korea.ac.kr 임성열 Ph.D.

'''
<설치 패키지 안내> 
pip install -U \
  "fastapi>=0.110" "uvicorn[standard]" "pydantic>=2" \
  "langchain>=0.2.6" "langchain-community>=0.2.6" "langchain-openai>=0.1.7" openai \
  "langchain-huggingface>=0.1.1" "sentence-transformers>=2.3.0" \
  "transformers>=4.40.0" "huggingface_hub>=0.23.0" \
  "sqlalchemy>=2.0" aiosqlite aiohttp pypdf python-multipart \
  beautifulsoup4 greenlet \
  "faiss-cpu>=1.7.4"

# torch 설치 (아래 중 택1)
pip install --index-url https://download.pytorch.org/whl/cpu torch       # CPU 전용
# pip install --index-url https://download.pytorch.org/whl/cu121 torch   # NVIDIA GPU, CUDA 12.1
# pip install --index-url https://download.pytorch.org/whl/cu118 torch   # NVIDIA GPU, CUDA 11.8
# pip install torch                                                      # macOS Apple Silicon(MPS)

<설치 패키지 설명>
1. 권장: 최신 pip
python -m pip install --upgrade pip

2. 서버/기본
pip install "fastapi>=0.110" "uvicorn[standard]>=0.30" "pydantic>=2"

3. LangChain 계열
pip install "langchain>=0.2.6" "langchain-community>=0.2.6" "langchain-openai>=0.1.7" \
           "langchain-huggingface>=0.1.1" openai>=1.37.0

4. 임베딩/LLM (Qwen용 HF, BGE-M3, 토치)
pip install "transformers>=4.40.0" "huggingface_hub>=0.23.0" "sentence-transformers>=2.3.0"

5. PyTorch: 환경에 맞춰 택1
nvidia-smi로 지원하는 CUDA 버전 확인하여 선택

pip install --index-url https://download.pytorch.org/whl/cpu torch       # CPU 전용
# pip install --index-url https://download.pytorch.org/whl/cu121 torch   # NVIDIA GPU, CUDA 12.1
# pip install --index-url https://download.pytorch.org/whl/cu118 torch   # NVIDIA GPU, CUDA 11.8
# pip install torch                                                      # macOS Apple Silicon(MPS)

6. 벡터DB
pip install "faiss-cpu>=1.7.4"
(macOS에서 pip 설치가 어려우면, conda 설치하여 사용해도 무관) conda install -c conda-forge faiss-cpu

7. DB/비동기
pip install "sqlalchemy>=2.0" "aiosqlite>=0.19" "aiohttp>=3.9"
선택: greenlet (일부 환경에서 필요할 수 있음)
pip install "greenlet>=3.0"

8. PDF/크롤/업로드
pip install "pypdf>=4.0" "python-multipart>=0.0.9"
선택: beautifulsoup4 (외부 크롤링 확장 시)
pip install "beautifulsoup4>=4.12"
'''
        
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.messages import HumanMessage
from huggingface_hub import login
from pypdf import PdfReader

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

import aiohttp
import tempfile
import os
import re
import json
import torch
from typing import Optional, List

# 환경변수: 경고/텔레메트리 억제 (지연 로딩과 함께 사용)
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

# 환경 변수 (실서비스는 .env 권장)
os.environ.setdefault("OPENAI_API_KEY", "your-openai-key-here")   # ← OpenAI 키 입력
# login("your-hf-token-here")  # ← HF 토큰 입력

# 내부 DB: SQLite 인-메모리(공유)
SQLITE_MEM_URL = "sqlite+aiosqlite:///file:internal_memdb?mode=memory&cache=shared&uri=true"
engine = create_async_engine(SQLITE_MEM_URL, future=True)

# FastAPI
app = FastAPI(
    title="RAG 기반 LLM API Server",
    description="내부/외부/PDF 벡터화 + LLM 질의 응답 (Internal은 SQLite 인메모리 시뮬레이션)",
    version="1.8.0"
)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 지연 초기화: Qwen LLM
_QWEN_TOKENIZER = None
_QWEN_MODEL = None

def get_qwen():
    """포크 이후 워커에서 최초 접근 시에만 토크나이저/모델 로딩."""
    global _QWEN_TOKENIZER, _QWEN_MODEL
    if _QWEN_TOKENIZER is None or _QWEN_MODEL is None:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        model_id = "Qwen/Qwen1.5-0.5B-Chat"
        _QWEN_TOKENIZER = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        _QWEN_MODEL = AutoModelForCausalLM.from_pretrained(
            model_id, trust_remote_code=True, dtype=torch.float32
        ).to("cpu")
        gc = _QWEN_MODEL.generation_config
        gc.do_sample = False
        gc.temperature = None
        gc.top_p = None
        gc.top_k = None
        gc.typical_p = None
        gc.num_beams = 1
        gc.use_cache = True
        _QWEN_MODEL.generation_config = gc
    return _QWEN_TOKENIZER, _QWEN_MODEL

def hf_generate_answer(prompt: str, max_input_tokens: int = 1536, max_new_tokens: int = 128) -> str:
    tokenizer, model = get_qwen()
    enc = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_input_tokens)
    input_ids = enc.input_ids.to(model.device)
    attention_mask = enc.attention_mask.to(model.device)
    with torch.no_grad():
        out = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            do_sample=False,
            num_beams=1,
            max_new_tokens=max_new_tokens,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
            use_cache=True
        )
    return tokenizer.decode(out[0], skip_special_tokens=True)

# 지연 초기화: BGE 임베딩 (신규 패키지)
class LazyBgeEmbeddings(Embeddings):
    """
    LangChain Embeddings 인터페이스를 따르는 지연 로딩 래퍼.
    내부는 langchain_huggingface.HuggingFaceEmbeddings를 사용하고,
    BGE 모델의 query/passages 인스트럭션을 직접 주입한다.
    """
    def __init__(self, model_name: str = "BAAI/bge-m3", device: str = "cpu", normalize: bool = True):
        self.model_name = model_name
        self.device = device
        self.normalize = normalize
        self._embedder: Optional[Embeddings] = None
        # BGE 권장 인스트럭션
        self.query_instruction = "Represent this sentence for searching relevant passages: "
        self.passage_instruction = "Represent this passage for retrieval: "

    def _ensure(self) -> Embeddings:
        if self._embedder is None:
            self._embedder = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={"device": self.device},
                encode_kwargs={"normalize_embeddings": self.normalize},
            )
        return self._embedder

    # ---- LangChain Embeddings API 구현 ----
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # passage instruction 주입
        inst_texts = [f"{self.passage_instruction}{t}" for t in texts]
        return self._ensure().embed_documents(inst_texts)

    def embed_query(self, text: str) -> List[float]:
        # query instruction 주입
        q = f"{self.query_instruction}{text}"
        return self._ensure().embed_query(q)

_BGE_LAZY: Optional[LazyBgeEmbeddings] = None
def get_bge_lazy() -> LazyBgeEmbeddings:
    """항상 같은 Lazy 래퍼를 반환(실 로딩은 첫 호출 시)."""
    global _BGE_LAZY
    if _BGE_LAZY is None:
        _BGE_LAZY = LazyBgeEmbeddings(model_name="BAAI/bge-m3", device="cpu", normalize=True)
    return _BGE_LAZY

def get_bge_real() -> LazyBgeEmbeddings:
    """업로드 시 실제 임베딩이 필요할 때 호출(포크 이후 안전)."""
    # ensure 호출은 embed_*에서 자동 수행되므로, 동일 객체 반환으로 충분
    return get_bge_lazy()

# 전역 벡터 스토어
VECTORSTORE_INTERNAL = None
VECTORSTORE_EXTERNAL = None
VECTORSTORE_PDF = None

# PDF 도우미 (정규화 강화)
def _normalize_pdf_text(txt: str) -> str:
    if not txt:
        return ""
    lig_map = {
        "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
        "\ufb03": "ffi", "\ufb04": "ffl"
    }
    for k, v in lig_map.items():
        txt = txt.replace(k, v)
    txt = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", txt)     # "atten-\n tion" -> "attention"
    txt = re.sub(r"\s*\n\s*", " ", txt)                  # 개행→공백
    txt = re.sub(r"\s{2,}", " ", txt)                    # 다중 공백 축소
    return txt.strip()

def load_paper(file_path: str) -> str:
    reader = PdfReader(file_path)
    raw = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
    return _normalize_pdf_text(raw)

# 앱 시작 시: 인메모리 DB 초기화(테이블/샘플 데이터) + 인덱스 로드
@app.on_event("startup")
async def init_sqlite_inmemory():
    async with engine.begin() as conn:
        await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            segment TEXT,
            country TEXT,
            note TEXT
        )"""))
        await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            sku TEXT,
            name TEXT,
            category TEXT,
            price REAL
        )"""))
        res = await conn.execute(text("SELECT COUNT(*) FROM customers"))
        count = res.scalar() or 0
        if count == 0:
            await conn.execute(text("""
                INSERT INTO customers (name, segment, country, note) VALUES
                ('Acorn Ltd', 'Enterprise', 'Korea', 'Top-tier client, prefers monthly reporting'),
                ('Birch Inc', 'SMB', 'USA', 'Pilot customer for Q3'),
                ('Cedar Co', 'Enterprise', 'Japan', 'Requires on-prem deployment')
            """))

        res2 = await conn.execute(text("SELECT COUNT(*) FROM products"))
        count2 = res2.scalar() or 0
        if count2 == 0:
            await conn.execute(text("""
                INSERT INTO products (sku, name, category, price) VALUES
                ('SKU-001', 'Vectorizer Pro', 'AI', 199.0),
                ('SKU-002', 'RAG Suite', 'AI', 499.0),
                ('SKU-003', 'DB Syncer', 'Integration', 149.0)
            """))

    # 인덱스 로드 (임베딩은 LazyBgeEmbeddings로 주입하여 실제 로딩을 지연)
    internal_path = "faiss_db/internal"
    if os.path.exists(f"{internal_path}/index.faiss") and os.path.exists(f"{internal_path}/index.pkl"):
        global VECTORSTORE_INTERNAL
        VECTORSTORE_INTERNAL = FAISS.load_local(
            internal_path,
            embeddings=get_bge_lazy(),  # ← Lazy 주입
            allow_dangerous_deserialization=True
        )
        print("✅ VECTORSTORE_INTERNAL 로드 완료")
    else:
        print("ℹ️ 내부 벡터 인덱스가 아직 없습니다. /upload-dbtable 로 생성하세요.")

    external_path = "faiss_db/external"
    if os.path.exists(f"{external_path}/index.faiss") and os.path.exists(f"{external_path}/index.pkl"):
        global VECTORSTORE_EXTERNAL
        VECTORSTORE_EXTERNAL = FAISS.load_local(
            external_path,
            embeddings=OpenAIEmbeddings(),  # OpenAI 임베딩은 토크나이저 의존X
            allow_dangerous_deserialization=True
        )
        print("✅ VECTORSTORE_EXTERNAL 로드 완료")
    else:
        print("ℹ️ 외부 벡터 인덱스가 아직 없습니다. /upload-topic 으로 생성하세요.")

    pdf_path = "faiss_db/pdf"
    if os.path.exists(f"{pdf_path}/index.faiss") and os.path.exists(f"{pdf_path}/index.pkl"):
        global VECTORSTORE_PDF
        VECTORSTORE_PDF = FAISS.load_local(
            pdf_path,
            embeddings=get_bge_lazy(),  # ← Lazy 주입
            allow_dangerous_deserialization=True
        )
        print("✅ VECTORSTORE_PDF 로드 완료")
    else:
        print("ℹ️ PDF 벡터 인덱스가 아직 없습니다. /upload-paper 로 생성하세요.")

# PDF 업로드/벡터화 (BGE + COSINE + 정규화)
@app.post("/upload-paper", summary="PDF 업로드 및 벡터화", tags=["PDF 처리"])
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 허용됩니다.")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        paper_text = load_paper(tmp_path)
        if not paper_text or len(paper_text) < 50:
            raise HTTPException(status_code=400, detail="PDF에서 텍스트를 추출하지 못했습니다. 스캔본이면 OCR 후 재업로드하세요.")

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        docs = splitter.create_documents([paper_text])

        global VECTORSTORE_PDF
        VECTORSTORE_PDF = FAISS.from_documents(
            docs, embedding=get_bge_real(), distance_strategy=DistanceStrategy.COSINE
        )

        os.makedirs("faiss_db/pdf", exist_ok=True)
        VECTORSTORE_PDF.save_local("faiss_db/pdf")

        return JSONResponse(content={"message": f"{len(docs)}개의 PDF 문서 벡터화 및 저장 완료"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 내부 DB 테이블 목록 (SQLite)
@app.get("/db-tables", summary="내부 DB 테이블 목록 조회 (SQLite in-memory)", tags=["내부 정보"])
async def list_tables():
    async with engine.connect() as conn:
        q = text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        rows = (await conn.execute(q)).fetchall()
        tables = [r[0] for r in rows]
        return JSONResponse(content={"tables": tables})

# 내부 테이블 → 벡터 DB (BGE + COSINE)
@app.post("/upload-dbtable", summary="DB 테이블 → 내부 벡터 DB(시뮬레이션)", tags=["내부 정보"])
async def upload_db_table(table: str = Query(..., description="벡터화할 테이블 이름")):
    try:
        if not re.fullmatch(r"[A-Za-z0-9_]+", table):
            raise HTTPException(status_code=400, detail="허용되지 않는 테이블 이름입니다.")

        async with engine.connect() as conn:
            result = await conn.execute(text(f'SELECT * FROM "{table}"'))
            rows = result.mappings().all()

        if not rows:
            return {"message": f"{table} 테이블에 데이터가 없습니다.", "docs": 0}

        texts = ["\n".join(f"{k}: {v}" for k, v in row.items()) for row in rows]

        splitter = RecursiveCharacterTextSplitter(chunk_size=150, chunk_overlap=20)
        docs = splitter.create_documents(texts)

        global VECTORSTORE_INTERNAL
        VECTORSTORE_INTERNAL = FAISS.from_documents(
            docs, embedding=get_bge_real(), distance_strategy=DistanceStrategy.COSINE
        )

        save_path = "faiss_db/internal"
        os.makedirs(save_path, exist_ok=True)
        VECTORSTORE_INTERNAL.save_local(save_path)

        return {
            "message": f"{table} 테이블에서 {len(docs)}개 청크 벡터화 및 저장 완료",
            "rows_loaded": len(rows),
            "docs": len(docs),
            "path": save_path,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 외부(웹) → 벡터화 (OpenAI 임베딩)
@app.post("/upload-topic", summary="웹 검색 → 외부 벡터 DB", tags=["외부 정보"])
async def upload_topic(topic: str = Query(..., description="검색할 주제")):
    try:
        NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "gbqzUVViEiF6WXhuq3gZ")
        NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "y0YXaa5unU")

        search_url = "https://openapi.naver.com/v1/search/news.json"
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        }

        want, display, start = 20, 20, 1
        items = []

        async with aiohttp.ClientSession() as session:
            while len(items) < want:
                params = {"query": topic, "display": display, "start": start, "sort": "date"}
                async with session.get(search_url, headers=headers, params=params) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

                batch = data.get("items", [])
                if not batch:
                    break

                def strip_tags(s: str) -> str:
                    return re.sub(r"</?b>", "", s or "")

                for it in batch:
                    it["title"] = strip_tags(it.get("title", ""))
                    it["description"] = strip_tags(it.get("description", ""))
                items.extend(batch)

                start += display
                if start > 1000:
                    break

        if not items:
            return {"message": "검색 결과가 없습니다.", "collected": 0}

        texts = [
            f"title: {it.get('title','')}\nlink: {it.get('link','')}\ndesc: {it.get('description','')}"
            for it in items
        ]
        texts = [t[:3000] for t in texts]

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
        docs = splitter.create_documents(texts)
        if not docs:
            return {"message": "벡터화할 문서가 없습니다.", "collected": len(items)}

        global VECTORSTORE_EXTERNAL
        VECTORSTORE_EXTERNAL = FAISS.from_documents(docs, embedding=OpenAIEmbeddings())

        save_path = "faiss_db/external"
        os.makedirs(save_path, exist_ok=True)
        VECTORSTORE_EXTERNAL.save_local(save_path)

        return {
            "message": f"{len(docs)}개의 웹 문서(청크) 벡터화 및 저장 완료",
            "collected": len(items),
            "sample_titles": [it.get("title", "") for it in items[:3]],
        }

    except aiohttp.ClientResponseError as e:
        raise HTTPException(status_code=e.status, detail=f"Naver API 오류: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# RAG 요청/응답 모델
class RAGRequest(BaseModel):
    prompt: str = Field(..., description="질문 프롬프트")
    source: str = Field(..., description="internal | external | pdf")
    top_k: int = Field(5, ge=1, description="검색할 결과 수")

class AnswerResponse(BaseModel):
    prompt: str
    response: str

# 공통 유틸
def extract_by_marker(text: str, start: str = "### ANSWER_START", end: str = "### ANSWER_END") -> Optional[str]:
    i = text.find(start)
    if i == -1:
        return None
    j = text.find(end, i + len(start))
    if j == -1:
        return None
    return text[i + len(start): j].strip()

def looks_boilerplate(s: str) -> bool:
    if not s:
        return True
    for p in (r"도와드릴 수 있", r"어떻게.*도와", r"무엇.*원하시", r"As an AI", r"I'm an AI", r"assist you"):
        if re.search(p, s, flags=re.IGNORECASE):
            return True
    return False

# 파이프라인별 전용 핸들러 (완전 분리)
# -------- INTERNAL 전용 --------
async def answer_internal(prompt: str, top_k: int) -> str:
    FIELD_ALIASES = {
        "segment": ["segment", "세그먼트", "고객 세그먼트", "그룹"],
        "country": ["country", "국가", "나라"],
        "note":    ["note", "메모", "비고", "특이사항"],
        "name":    ["name", "고객명", "회사명", "이름"],
        "sku":     ["sku", "제품코드", "모델명"],
        "category":["category", "카테고리", "분류"],
        "price":   ["price", "가격"],
    }
    def _canonical_field_from_question(q: str) -> Optional[str]:
        nq = (q or "").lower()
        for key, aliases in FIELD_ALIASES.items():
            if any(a.lower() in nq for a in aliases):
                return key
        return None
    def _parse_kv_block(text_block: str) -> dict:
        kv = {}
        for line in (text_block or "").splitlines():
            m = re.match(r"\s*([A-Za-z가-힣0-9_]+)\s*:\s*(.*)\s*$", line)
            if not m: continue
            k = m.group(1).strip().lower(); v = m.group(2).strip()
            for canon, aliases in FIELD_ALIASES.items():
                if k == canon or k in [a.lower() for a in aliases]:
                    k = canon; break
            kv[k] = v
        return kv

    async def _get_known_entities():
        customers, prod_names, prod_skus = [], [], []
        async with engine.connect() as conn:
            rows = (await conn.execute(text("SELECT name FROM customers"))).fetchall()
            customers = [r[0] for r in rows]
            rows = (await conn.execute(text("SELECT name, sku FROM products"))).fetchall()
            for n, s in rows:
                prod_names.append(n); prod_skus.append(s)
        return {"customers": customers, "product_names": prod_names, "product_skus": prod_skus}

    def _determine_type(candidate: str, ents: dict) -> Optional[str]:
        c = (candidate or "").lower()
        if any((c == (n or "").lower()) for n in ents.get("customers", [])): return "customer"
        if any((c == (s or "").lower()) for s in ents.get("product_skus", [])): return "product"
        if any((c == (n or "").lower()) for n in ents.get("product_names", [])): return "product"
        if any((c in (n or "").lower()) for n in ents.get("customers", [])): return "customer"
        if any((c in (s or "").lower()) for s in ents.get("product_skus", [])): return "product"
        if any((c in (n or "").lower()) for n in ents.get("product_names", [])): return "product"
        return None

    def _extract_entity_candidates_from_context(ctx: str, known: List[str], limit=5):
        cand = []; low_known = [k.lower() for k in known if k]
        for block in re.split(r"\n\s*\n", ctx or ""):
            b = block.lower()
            hits = [k for k in low_known if k in b]
            for h in hits:
                idx = low_known.index(h); orig = known[idx]
                if orig not in cand: cand.append(orig)
            if len(cand) >= limit: break
        return cand

    # 1) 의미 리트리벌(임계컷X, fetch_k↑, MMR 1회)
    fetch_k = max(top_k * 6, 32)
    try:
        docs = [d for d, _ in VECTORSTORE_INTERNAL.similarity_search_with_score(prompt, k=fetch_k)]
    except Exception:
        docs = VECTORSTORE_INTERNAL.similarity_search(prompt, k=fetch_k)
    try:
        docs = VECTORSTORE_INTERNAL.max_marginal_relevance_search(prompt, k=min(len(docs), top_k), fetch_k=min(fetch_k, 48))
    except Exception:
        docs = docs[:top_k]

    # 2) 컨텍스트
    MAX_CHARS = 1200
    buf, total = [], 0
    for d in docs:
        pc = (getattr(d, "page_content", "") or "").strip()
        if not pc: continue
        take = min(len(pc), MAX_CHARS - total)
        if take <= 0: break
        buf.append(pc[:take]); total += take
    context = "\n\n".join(buf).strip()

    # 3) 검증/추출
    entities = await _get_known_entities()
    field = _canonical_field_from_question(prompt)
    known_all = entities["customers"] + entities["product_names"] + entities["product_skus"]
    ent_candidates = _extract_entity_candidates_from_context(context, known_all, limit=5)

    q_lower = (prompt or "").lower()
    query_ent = next((n for n in known_all if n and n.lower() in q_lower), None)
    if query_ent and query_ent not in ent_candidates:
        ent_candidates = [query_ent] + ent_candidates

    if not ent_candidates and not field:
        return "지식베이스에서 답을 찾을 수 없습니다."

    def _rule_answer(ctx: str) -> Optional[str]:
        if not field: return None
        for cand in ent_candidates:
            etype = _determine_type(cand, entities) or ""
            for block in re.split(r"\n\s*\n", ctx or ""):
                kv = _parse_kv_block(block)
                if not kv: continue
                if etype == "customer":
                    name = kv.get("name", "")
                    if name and cand.lower() in name.lower() and field in kv and kv[field]:
                        return kv[field]
                elif etype == "product":
                    sku = kv.get("sku", ""); pname = kv.get("name", "")
                    if ((sku and cand.lower() in sku.lower()) or (pname and cand.lower() in pname.lower())) and field in kv and kv[field]:
                        return kv[field]
                else:
                    name = kv.get("name", ""); sku = kv.get("sku", "")
                    if ((name and cand.lower() in name.lower()) or (sku and cand.lower() in sku.lower())) and field in kv and kv[field]:
                        return kv[field]
        return None

    rb = _rule_answer(context)
    if rb: return rb

    if field:
        for cand in ent_candidates:
            etype = _determine_type(cand, entities)
            if not etype: continue
            async with engine.connect() as conn:
                if etype == "customer":
                    row = (await conn.execute(
                        text("SELECT name, segment, country, note FROM customers WHERE lower(name)=lower(:n)"),
                        {"n": cand}
                    )).first()
                    if row:
                        mapping = {"name": row[0], "segment": row[1], "country": row[2], "note": row[3]}
                        val = mapping.get(field)
                        if val is not None: return str(val)
                else:
                    row = (await conn.execute(
                        text("""SELECT sku, name, category, price FROM products 
                                WHERE lower(sku)=lower(:e) OR lower(name)=lower(:e)"""),
                        {"e": cand}
                    )).first()
                    if row:
                        mapping = {"sku": row[0], "name": row[1], "category": row[2], "price": str(row[3])}
                        val = mapping.get(field)
                        if val is not None: return str(val)

    if not context:
        return "지식베이스에서 답을 찾을 수 없습니다."
    full_prompt = (
        "다음은 내부 데이터이다. 이 데이터에 '직접적으로 명시된' 사실만 근거로 답하라.\n"
        "- 답변은 한 문장으로만 작성하라.\n"
        "- 데이터에 없는 내용은 'N/A'를 '정확히' 그대로 출력하라.\n\n"
        f"[데이터]\n{context}\n\n"
        f"[질문]\n{prompt}\n\n"
        "### ANSWER_START\n"
        "### ANSWER_END"
    )
    raw = hf_generate_answer(full_prompt, max_input_tokens=1536, max_new_tokens=72).strip()
    answer = extract_by_marker(raw) or "N/A"
    final = (answer or "").strip()
    if final.upper() == "N/A" or looks_boilerplate(final) or not final:
        final = "지식베이스에서 답을 찾을 수 없습니다."
    return final

# -------- PDF 전용 (BGE + COSINE + 정규화 + 보강 질의) --------
async def answer_pdf(prompt: str, top_k: int) -> str:
    if VECTORSTORE_PDF is None:
        return "지식베이스에서 답을 찾을 수 없습니다."

    fetch_k = max(top_k * 6, 32)

    # ❶ 기본 질의
    docs = []
    try:
        docs_scores = VECTORSTORE_PDF.similarity_search_with_score(prompt, k=fetch_k)
        docs = [d for d, _ in docs_scores]
    except Exception:
        docs = VECTORSTORE_PDF.similarity_search(prompt, k=fetch_k)

    # ❷ 보강 질의(ASCII 키워드)
    ascii_q = re.sub(r"[^A-Za-z0-9\s]+", " ", prompt or "").strip()
    if ascii_q and ascii_q.lower() != (prompt or "").lower():
        try:
            extra = VECTORSTORE_PDF.similarity_search(ascii_q, k=max(8, fetch_k // 2))
            seen, merged = set(), []
            for d in (docs + extra):
                key = getattr(d, "page_content", "")
                if key and key not in seen:
                    seen.add(key); merged.append(d)
            docs = merged
        except Exception:
            pass

    if not docs:
        return "지식베이스에서 답을 찾을 수 없습니다."

    try:
        docs = VECTORSTORE_PDF.max_marginal_relevance_search(prompt, k=min(len(docs), top_k), fetch_k=min(fetch_k, 48))
    except Exception:
        docs = docs[:top_k]

    MAX_CHARS = 2500
    buf, total = [], 0
    for d in docs:
        pc = (getattr(d, "page_content", "") or "").strip()
        if not pc: continue
        take = min(len(pc), MAX_CHARS - total)
        if take <= 0: break
        buf.append(pc[:take]); total += take
    context = "\n\n".join(buf).strip()
    if not context:
        return "지식베이스에서 답을 찾을 수 없습니다."

    llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
    full_prompt = (
        "다음은 PDF에서 추출한 텍스트이다. 이 범위 밖의 지식은 사용하지 말고, "
        "직접적으로 근거가 없으면 정확히 'N/A'를 출력하라.\n"
        f"{context}\n\n"
        f"질문: {prompt}\n\n"
        "### ANSWER_START\n"
        "<정답 또는 N/A>\n"
        "### ANSWER_END"
    )
    raw = llm.invoke([HumanMessage(content=full_prompt)]).content.strip()
    answer = extract_by_marker(raw) or "N/A"
    return "지식베이스에서 답을 찾을 수 없습니다." if answer.strip().upper() == "N/A" else answer.strip()

# -------- EXTERNAL 전용 --------
async def answer_external(prompt: str, top_k: int) -> str:
    if VECTORSTORE_EXTERNAL is None:
        return "웹 검색 기반 지식베이스에서 충분한 결과를 찾지 못했습니다. 키워드를 달리하여 다시 시도해 주십시오."

    has_korean = any('\uac00' <= ch <= '\ud7a3' for ch in prompt or "")
    merged = []

    def _limited_context(docs, limit_chars=4000):
        buf, total = [], 0
        for d in docs:
            pc = getattr(d, "page_content", "") or ""
            if not pc.strip(): continue
            if total + len(pc) > limit_chars: break
            buf.append(pc); total += len(pc)
        return "\n\n".join(buf)

    docs1 = VECTORSTORE_EXTERNAL.similarity_search(prompt, k=max(5, top_k))
    merged.extend(docs1)
    try:
        if has_korean:
            q_en = prompt  # 필요 시 번역 훅
            docs2 = VECTORSTORE_EXTERNAL.similarity_search(q_en, k=max(5, top_k))
            merged.extend(docs2)
    except Exception:
        pass

    seen, uniq = set(), []
    for d in merged:
        key = getattr(d, "page_content", "")
        if key and key not in seen:
            seen.add(key); uniq.append(d)

    if not uniq:
        return "웹 검색 기반 지식베이스에서 충분한 결과를 찾지 못했습니다. 키워드를 달리하여 다시 시도해 주십시오."

    context = _limited_context(uniq, limit_chars=4000)
    if not context.strip():
        return "웹 검색 기반 지식베이스에서 충분한 결과를 찾지 못했습니다. 키워드를 달리하여 다시 시도해 주십시오."

    llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    full_prompt = (
        "아래 컨텍스트에서만 답변을 작성하시오. 컨텍스트에 없는 내용은 추측하지 마시오. "
        "가능하면 문장 끝에 간단한 출처 표기를 괄호로 덧붙이시오(예: (출처 1), (출처 2)).\n"
        f"{context}\n\n"
        f"질문: {prompt}\n\n"
        "### ANSWER_START\n"
        "<정답(간결한 한국어, 필요 시 간단한 출처 표기)>\n"
        "### ANSWER_END"
    )
    raw = llm.invoke([HumanMessage(content=full_prompt)]).content.strip()
    answer = extract_by_marker(raw) or raw
    return (answer or "").strip() or \
        "웹 검색 기반 지식베이스에서 충분한 결과를 찾지 못했습니다. 키워드를 달리하여 다시 시도해 주십시오."

# RAG 질의 (파이프라인 분리 호출)
@app.post("/rag-query", response_model=AnswerResponse, summary="LLM + 벡터 DB 질의", tags=["질의 응답"])
async def rag_query(rag_request: RAGRequest = Body(...)):
    src = (rag_request.source or "").lower().strip()
    top_k = max(5, rag_request.top_k or 5)

    if src == "internal":
        if VECTORSTORE_INTERNAL is None:
            raise HTTPException(400, "❗ 내부 벡터가 없습니다. /upload-dbtable 먼저 실행하세요.")
        resp = await answer_internal(rag_request.prompt, top_k)

    elif src == "pdf":
        if VECTORSTORE_PDF is None:
            raise HTTPException(400, "❗ PDF 벡터가 없습니다. /upload-paper 먼저 실행하세요.")
        resp = await answer_pdf(rag_request.prompt, top_k)

    elif src == "external":
        if VECTORSTORE_EXTERNAL is None:
            raise HTTPException(400, "❗ 외부 벡터가 없습니다. /upload-topic 먼저 실행하세요.")
        resp = await answer_external(rag_request.prompt, top_k)

    else:
        raise HTTPException(400, "❗ source는 'internal' | 'external' | 'pdf' 중 하나여야 합니다.")

    return AnswerResponse(prompt=rag_request.prompt, response=resp)

# 내부 셀프 테스트 (환각 억제/정확도 확인)
@app.get("/selftest-internal", summary="내부 파이프라인 셀프 테스트", tags=["내부 정보"])
async def selftest_internal():
    global VECTORSTORE_INTERNAL
    if VECTORSTORE_INTERNAL is None:
        await upload_db_table(table="customers")

    q1 = "Acorn Ltd의 고객 세그먼트는 무엇인가?"
    a1 = (await rag_query(RAGRequest(prompt=q1, source="internal", top_k=5))).response
    q2 = "Acorn Ltd의 본사 주소 우편번호는 무엇인가?"
    a2 = (await rag_query(RAGRequest(prompt=q2, source="internal", top_k=5))).response
    q3 = "Attention이 무엇인가?"
    a3 = (await rag_query(RAGRequest(prompt=q3, source="internal", top_k=5))).response

    def ok_contains(ans: str, needle: str) -> bool:
        return needle.lower() in (ans or "").lower()

    return {
        "q_exist": q1, "a_exist": a1, "pass_exist": ok_contains(a1, "Enterprise"),
        "q_not_exist": q2, "a_not_exist": a2, "pass_not_exist": ok_contains(a2, "지식베이스에서 답을 찾을 수 없습니다."),
        "q_out_of_schema": q3, "a_out_of_schema": a3, "pass_out_of_schema": ok_contains(a3, "지식베이스에서 답을 찾을 수 없습니다."),
        "note": "exist는 실제 값, not_exist/out_of_schema는 '지식베이스에서 답을 찾을 수 없습니다.' 기대"
    }

# 디버그: 벡터스토어 상태 확인
@app.get("/debug-stats", summary="현재 벡터스토어 상태", tags=["디버그"])
async def debug_stats():
    def _vs_stats(vs, name):
        if vs is None:
            return {"name": name, "loaded": False}
        try:
            n = len(getattr(vs, "docstore")._dict)  # 내부 구조 접근(버전별 차이 가능)
        except Exception:
            n = None
        sample = None
        try:
            if n:
                any_key = next(iter(vs.docstore._dict.keys()))
                sample = vs.docstore._dict[any_key].page_content[:200]
        except Exception:
            pass
        return {"name": name, "loaded": True, "docs": n, "sample": sample}

    return {
        "internal": _vs_stats(VECTORSTORE_INTERNAL, "internal"),
        "pdf": _vs_stats(VECTORSTORE_PDF, "pdf"),
        "external": _vs_stats(VECTORSTORE_EXTERNAL, "external"),
    }


## 테스트 테이블 구조 및 데이터 정보
# customers
# | id | name      | segment    | country | note                                       |
# | -: | --------- | ---------- | ------- | ------------------------------------------ |
# |  1 | Acorn Ltd | Enterprise | Korea   | Top-tier client, prefers monthly reporting |
# |  2 | Birch Inc | SMB        | USA     | Pilot customer for Q3                      |
# |  3 | Cedar Co  | Enterprise | Japan   | Requires on-prem deployment                |

# products
# | id | sku     | name           | category    |  price |
# | -: | ------- | -------------- | ----------- | -----: |
# |  1 | SKU-001 | Vectorizer Pro | AI          | 199.00 |
# |  2 | SKU-002 | RAG Suite      | AI          | 499.00 |
# |  3 | SKU-003 | DB Syncer      | Integration | 149.00 |


## 사용 방법 요약
# 1. 서버 실행 후, 자동으로 SQLite 인-메모리 DB가 초기화
# 2. GET /db-tables로 샘플 테이블(customers, products) 확인
# 3. POST /upload-dbtable?table=customers → 내부 벡터 인덱스 생성
# 4. POST /rag-query
#    {"prompt":"Acorn Ltd의 세그먼트는?","source":"internal"}
#    데이터에 없는 질문은 정확히 차단되어 "지식베이스에서 답을 찾을 수 없습니다." 반환
#5. 빠르게 점검하려면 GET /selftest-internal 호출'''

# 실행 명령어 예시:
# uvicorn practice_RAG_App_main_fixed:app --port 8003 --reload
