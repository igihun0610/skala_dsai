import os
import traceback
import pickle
import asyncio
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from loguru import logger

try:
    import faiss
    from sentence_transformers import SentenceTransformer
except ImportError:
    logger.error("faiss-cpu 또는 sentence-transformers가 설치되지 않았습니다.")
    faiss = None
    SentenceTransformer = None

from langchain.docstore.document import Document
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OllamaEmbeddings

from ..config.settings import settings
from ..config.database import AsyncSessionLocal, VectorChunk


class VectorSearchService:
    """FAISS 기반 벡터 검색 서비스"""

    def __init__(self, embedding_model_name: str = None):
        self.embedding_model_name = embedding_model_name or settings.embedding_model
        self.vector_db_path = Path(settings.vector_db_path)
        self.vector_db_path.mkdir(parents=True, exist_ok=True)

        # 임베딩 모델 초기화
        self._embedding_model = None
        self._faiss_index = None
        self._document_store = {}
        self._metadata_store = {}

        self.executor = ThreadPoolExecutor(max_workers=4)

    @property
    def embedding_model(self):
        """지연 로딩을 통한 Ollama 임베딩 모델 초기화"""
        if self._embedding_model is None:
            try:
                self._embedding_model = OllamaEmbeddings(
                    model="bge-m3:latest",
                    base_url="http://localhost:11434"
                )
                logger.info(f"Ollama 임베딩 모델 로드 완료: bge-m3:latest")
            except Exception as e:
                logger.error(f"Ollama 임베딩 모델 로드 실패: {e}")
                raise
        return self._embedding_model

    async def create_index_from_documents(self, documents: List[Document], index_name: str = "default") -> bool:
        """문서들로부터 벡터 인덱스 생성"""
        try:
            if not documents:
                logger.warning("생성할 문서가 없습니다.")
                return False

            logger.info(f"{len(documents)}개 문서로부터 벡터 인덱스 생성 시작")

            # FAISS 벡터스토어 생성
            vectorstore = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                FAISS.from_documents,
                documents,
                self.embedding_model
            )

            # 인덱스 저장
            index_path = self.vector_db_path / index_name
            index_path.mkdir(parents=True, exist_ok=True)

            def save_vectorstore():
                return vectorstore.save_local(str(index_path))

            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                save_vectorstore
            )

            self._faiss_index = vectorstore
            logger.info(f"벡터 인덱스 생성 및 저장 완료: {index_path}")

            # 메타데이터를 데이터베이스에 저장
            await self._save_chunk_metadata(documents, index_name)

            return True

        except Exception as e:
            logger.error(f"벡터 인덱스 생성 실패: {e}")
            return False

    async def load_index(self, index_name: str = "default") -> bool:
        """저장된 벡터 인덱스 로드"""
        try:
            index_path = self.vector_db_path / index_name

            if not (index_path / "index.faiss").exists():
                logger.warning(f"벡터 인덱스가 존재하지 않습니다: {index_path}")
                return False

            # functools.partial을 사용하여 키워드 인자를 포함한 함수를 만듭니다.
            import functools
            load_with_args = functools.partial(
                FAISS.load_local,
                str(index_path),
                self.embedding_model,
                allow_dangerous_deserialization=True
            )

            # 비동기 실행
            self._faiss_index = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                load_with_args
            )

            logger.info(f"벡터 인덱스 로드 완료: {index_path}")
            return True

        except Exception:
            logger.error(f"벡터 인덱스 로드 실패: {traceback.format_exc()}")
            return False

    async def reload_index(self, index_name: str = "default") -> bool:
        """벡터 인덱스 다시 로드"""
        logger.info(f"벡터 인덱스 재로드 시작: {index_name}")
        return await self.load_index(index_name)

    async def add_documents(self, documents: List[Document], index_name: str = "default") -> bool:
        """기존 인덱스에 문서 추가"""
        try:
            if not self._faiss_index:
                return await self.create_index_from_documents(documents, index_name)

            # 기존 인덱스에 문서 추가
            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._faiss_index.add_documents,
                documents
            )

            # 인덱스 저장
            index_path = self.vector_db_path / index_name

            def save_faiss_index():
                return self._faiss_index.save_local(str(index_path))

            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                save_faiss_index
            )

            # 메타데이터 저장
            await self._save_chunk_metadata(documents, index_name)

            logger.info(f"{len(documents)}개 문서가 인덱스에 추가됨")
            return True

        except Exception as e:
            logger.error(f"문서 추가 실패: {e}")
            return False

    async def search(self,
                    query: str,
                    top_k: int = 5,
                    score_threshold: float = 0.0,
                    filter_metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """유사도 검색"""
        try:
            logger.info(f"벡터 검색 시작 - 쿼리: {query[:50]}...")

            if not self._faiss_index:
                logger.warning("로드된 벡터 인덱스가 없습니다. 다시 로드를 시도합니다.")
                try:
                    loaded = await asyncio.wait_for(
                        self.reload_index(),
                        timeout=30.0
                    )
                    if not loaded:
                        logger.warning("벡터 인덱스 로드 실패. 빈 결과를 반환합니다.")
                        return []
                    logger.info("벡터 인덱스 재로드 완료")
                except asyncio.TimeoutError:
                    logger.error("벡터 인덱스 재로드 타임아웃 (30초)")
                    return []

            logger.info("벡터 유사도 검색 실행 중...")
            logger.info(f"FAISS 인덱스 상태: {self._faiss_index is not None}")
            logger.info(f"검색 매개변수 - 쿼리 길이: {len(query)}, top_k: {top_k}")

            # 임베딩 생성 테스트 (더 짧은 타임아웃)
            try:
                logger.info("임베딩 생성 테스트 중...")
                def embed_with_timeout():
                    return self.embedding_model.embed_query(query[:50])  # 더 짧게 테스트

                test_embedding = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        self.executor,
                        embed_with_timeout
                    ),
                    timeout=5.0  # 5초로 단축
                )
                logger.info(f"임베딩 생성 성공 - 차원: {len(test_embedding)}")
            except asyncio.TimeoutError:
                logger.error("임베딩 생성 타임아웃 (5초) - 벡터 검색 건너뛰기")
                return []
            except Exception as e:
                logger.error(f"임베딩 생성 실패: {e}")
                return []

            # 유사도 검색 실행
            logger.info("FAISS 유사도 검색 시작...")
            results = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._faiss_index.similarity_search_with_score,
                    query,
                    top_k
                ),
                timeout=30.0
            )
            logger.info(f"FAISS 검색 완료 - {len(results)}개 결과")

            # 결과 변환
            search_results = []
            for doc, score in results:
                if score >= score_threshold:  # 임계값 필터링
                    result = {
                        "content": doc.page_content,
                        "score": float(score),
                        "metadata": doc.metadata
                    }

                    # 메타데이터 필터링
                    if filter_metadata:
                        if not self._match_metadata_filter(doc.metadata, filter_metadata):
                            continue

                    search_results.append(result)

            logger.info(f"검색 완료: {len(search_results)}개 결과")
            return search_results

        except Exception as e:
            logger.error(f"검색 실패: {e}")
            return []

    async def search_with_mmr(self,
                             query: str,
                             top_k: int = 5,
                             fetch_k: int = 20,
                             lambda_mult: float = 0.5) -> List[Dict[str, Any]]:
        """최대 주변 관련성(MMR) 검색"""
        try:
            if not self._faiss_index:
                logger.warning("로드된 벡터 인덱스가 없습니다.")
                return []

            # MMR 검색 실행
            results = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._faiss_index.max_marginal_relevance_search,
                query,
                top_k,
                fetch_k,
                lambda_mult
            )

            # 결과 변환
            search_results = []
            for doc in results:
                search_results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata
                })

            logger.info(f"MMR 검색 완료: {len(search_results)}개 결과")
            return search_results

        except Exception as e:
            logger.error(f"MMR 검색 실패: {e}")
            return []

    async def get_index_stats(self, index_name: str = "default") -> Dict[str, Any]:
        """인덱스 통계 정보"""
        try:
            index_path = self.vector_db_path / index_name

            stats = {
                "index_name": index_name,
                "exists": (index_path / "index.faiss").exists(),
                "path": str(index_path),
                "total_documents": 0,
                "index_size_mb": 0.0
            }

            if stats["exists"]:
                # 인덱스 파일 크기
                faiss_file = index_path / "index.faiss"
                pkl_file = index_path / "index.pkl"

                if faiss_file.exists():
                    stats["index_size_mb"] += faiss_file.stat().st_size / (1024 * 1024)
                if pkl_file.exists():
                    stats["index_size_mb"] += pkl_file.stat().st_size / (1024 * 1024)

                # 문서 수 (인덱스가 로드되어 있는 경우)
                if self._faiss_index:
                    stats["total_documents"] = self._faiss_index.index.ntotal

            return stats

        except Exception as e:
            logger.error(f"인덱스 통계 조회 실패: {e}")
            return {"error": str(e)}

    async def delete_index(self, index_name: str = "default") -> bool:
        """인덱스 삭제"""
        try:
            index_path = self.vector_db_path / index_name

            if index_path.exists():
                import shutil
                shutil.rmtree(index_path)
                logger.info(f"인덱스 삭제 완료: {index_name}")

                # 메모리에서도 제거
                if self._faiss_index:
                    self._faiss_index = None

                return True
            else:
                logger.warning(f"삭제할 인덱스가 없습니다: {index_name}")
                return False

        except Exception as e:
            logger.error(f"인덱스 삭제 실패: {e}")
            return False

    async def _save_chunk_metadata(self, documents: List[Document], index_name: str):
        """청크 메타데이터를 데이터베이스에 저장"""
        try:
            async with AsyncSessionLocal() as session:
                for i, doc in enumerate(documents):
                    chunk = VectorChunk(
                        document_id=doc.metadata.get("document_id"),
                        chunk_index=i,
                        chunk_text=doc.page_content,
                        chunk_embedding_id=f"{index_name}_{i}",
                        page_number=doc.metadata.get("page_number"),
                        section_id=doc.metadata.get("section_id"),
                        token_count=len(doc.page_content.split())
                    )
                    session.add(chunk)

                await session.commit()
                logger.info(f"{len(documents)}개 청크 메타데이터 저장 완료")

        except Exception as e:
            logger.error(f"청크 메타데이터 저장 실패: {e}")

    def _match_metadata_filter(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """메타데이터 필터링 매칭"""
        for key, expected_value in filters.items():
            if key not in metadata:
                return False

            actual_value = metadata[key]

            if isinstance(expected_value, list):
                if actual_value not in expected_value:
                    return False
            elif actual_value != expected_value:
                return False

        return True

    async def reindex_all_documents(self, index_name: str = "default") -> bool:
        """모든 문서 재인덱싱"""
        try:
            # 기존 인덱스 삭제
            await self.delete_index(index_name)

            # 데이터베이스에서 모든 청크 조회
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(VectorChunk).order_by(VectorChunk.document_id, VectorChunk.chunk_index)
                )
                chunks = result.scalars().all()

            if not chunks:
                logger.warning("재인덱싱할 청크가 없습니다.")
                return False

            # LangChain Document 객체로 변환
            documents = []
            for chunk in chunks:
                doc = Document(
                    page_content=chunk.chunk_text,
                    metadata={
                        "document_id": chunk.document_id,
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.page_number,
                        "section_id": chunk.section_id
                    }
                )
                documents.append(doc)

            # 인덱스 재생성
            success = await self.create_index_from_documents(documents, index_name)

            if success:
                logger.info(f"{len(documents)}개 문서로 재인덱싱 완료")

            return success

        except Exception as e:
            logger.error(f"재인덱싱 실패: {e}")
            return False


# 전역 벡터 검색 서비스 인스턴스
_vector_service: Optional[VectorSearchService] = None

async def get_vector_service() -> VectorSearchService:
    """벡터 검색 서비스 싱글톤 인스턴스 반환"""
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorSearchService()

        # CRITICAL: 안전한 인덱스 로드 - 타임아웃과 예외 처리
        try:
            import asyncio
            loaded = await asyncio.wait_for(
                _vector_service.load_index(),
                timeout=30.0
            )
            if loaded:
                logger.info("✅ 기존 벡터 인덱스 로드 완료")
            else:
                logger.info("🔍 벡터 인덱스가 아직 생성되지 않았습니다. 첫 문서 업로드 시 생성됩니다.")
        except asyncio.TimeoutError:
            logger.warning("⚠️ 벡터 인덱스 로드 타임아웃 (30초) - 첫 사용 시 생성됩니다")
        except Exception as e:
            logger.warning(f"⚠️ 벡터 인덱스 로드 실패: {e} - 첫 사용 시 생성됩니다")
            # 실패해도 서비스는 계속 사용 가능 (새 인덱스 생성 가능)

    return _vector_service