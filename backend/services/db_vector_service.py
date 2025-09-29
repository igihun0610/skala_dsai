import asyncio
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from loguru import logger
from sentence_transformers import SentenceTransformer

from ..config.database import get_db
from ..config.settings import settings


class DBVectorService:
    """내부 데이터베이스 테이블을 벡터화하여 검색 가능하게 만드는 서비스"""

    def __init__(self):
        self.embedding_model = None
        self._embedding_model_loaded = False

    async def _load_embedding_model(self):
        """임베딩 모델 로드 (지연 로딩)"""
        if not self._embedding_model_loaded:
            try:
                self.embedding_model = SentenceTransformer(settings.embedding_model)
                self._embedding_model_loaded = True
                logger.info(f"DB 벡터화용 임베딩 모델 로드 완료: {settings.embedding_model}")
            except Exception as e:
                logger.error(f"임베딩 모델 로드 실패: {e}")
                raise

    async def vectorize_document_metadata(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """문서 메타데이터를 벡터화하여 검색 가능한 형태로 변환"""
        await self._load_embedding_model()

        try:
            # 문서 메타데이터 조회
            result = await db.execute(text("""
                SELECT
                    id,
                    filename,
                    document_type,
                    file_size,
                    upload_date,
                    processing_status,
                    product_family,
                    product_model,
                    version,
                    language,
                    page_count
                FROM documents
                WHERE processing_status = 'completed'
            """))

            documents = result.fetchall()
            vectorized_docs = []

            for doc in documents:
                # 검색 가능한 텍스트 조합
                searchable_text = self._create_searchable_text(doc)

                # 임베딩 생성
                embedding = self.embedding_model.encode(searchable_text)

                vectorized_docs.append({
                    "id": doc.id,
                    "source_type": "document_metadata",
                    "content": searchable_text,
                    "embedding": embedding.tolist(),
                    "metadata": {
                        "filename": doc.filename,
                        "document_type": doc.document_type,
                        "upload_date": str(doc.upload_date),
                        "file_size": doc.file_size,
                        "product_family": doc.product_family or "",
                        "product_model": doc.product_model or "",
                        "version": doc.version or "",
                        "language": doc.language or "",
                        "page_count": doc.page_count or 0
                    }
                })

            logger.info(f"문서 메타데이터 {len(vectorized_docs)}개 벡터화 완료")
            return vectorized_docs

        except Exception as e:
            logger.error(f"문서 메타데이터 벡터화 실패: {e}")
            raise

    async def vectorize_query_history(self, db: AsyncSession, limit: int = 100) -> List[Dict[str, Any]]:
        """최근 질의 기록을 벡터화하여 FAQ 형태로 활용"""
        await self._load_embedding_model()

        try:
            # 최근 질의 기록 조회 (높은 confidence 위주)
            result = await db.execute(text("""
                SELECT
                    id,
                    question,
                    answer,
                    confidence,
                    user_role,
                    response_time_ms,
                    created_at
                FROM query_logs
                WHERE confidence > 0.7
                ORDER BY confidence DESC, created_at DESC
                LIMIT :limit
            """), {"limit": limit})

            queries = result.fetchall()
            vectorized_queries = []

            for query in queries:
                # Q&A 형태로 검색 텍스트 구성
                searchable_text = f"질문: {query.question}\n답변: {query.answer}"

                # 임베딩 생성
                embedding = self.embedding_model.encode(searchable_text)

                vectorized_queries.append({
                    "id": f"query_{query.id}",
                    "source_type": "query_history",
                    "content": searchable_text,
                    "embedding": embedding.tolist(),
                    "metadata": {
                        "question": query.question,
                        "answer": query.answer,
                        "confidence": float(query.confidence),
                        "user_role": query.user_role,
                        "response_time_ms": query.response_time_ms,
                        "created_at": str(query.created_at)
                    }
                })

            logger.info(f"질의 기록 {len(vectorized_queries)}개 벡터화 완료")
            return vectorized_queries

        except Exception as e:
            logger.error(f"질의 기록 벡터화 실패: {e}")
            raise

    async def search_vectorized_data(
        self,
        query_text: str,
        vectorized_data: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """벡터화된 데이터에서 유사한 항목 검색"""
        await self._load_embedding_model()

        try:
            # 질의 임베딩 생성
            query_embedding = self.embedding_model.encode(query_text)

            # 코사인 유사도 계산
            import numpy as np

            similarities = []
            for item in vectorized_data:
                item_embedding = np.array(item["embedding"])
                similarity = np.dot(query_embedding, item_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(item_embedding)
                )
                similarities.append((similarity, item))

            # 유사도 순으로 정렬
            similarities.sort(key=lambda x: x[0], reverse=True)

            # 상위 k개 결과 반환
            results = []
            for similarity, item in similarities[:top_k]:
                result = item.copy()
                result["similarity"] = float(similarity)
                results.append(result)

            logger.info(f"벡터 검색 완료: {len(results)}개 결과")
            return results

        except Exception as e:
            logger.error(f"벡터 검색 실패: {e}")
            raise

    def _create_searchable_text(self, doc) -> str:
        """문서 메타데이터로부터 검색 가능한 텍스트 생성"""
        parts = []

        # 파일명 (확장자 제거)
        filename_without_ext = doc.filename.rsplit('.', 1)[0] if '.' in doc.filename else doc.filename
        parts.append(f"파일명: {filename_without_ext}")

        # 문서 타입
        if doc.document_type:
            parts.append(f"타입: {doc.document_type}")

        # 제품 정보
        if doc.product_family:
            parts.append(f"제품군: {doc.product_family}")

        if doc.product_model:
            parts.append(f"모델: {doc.product_model}")

        if doc.version:
            parts.append(f"버전: {doc.version}")

        # 언어
        if doc.language:
            parts.append(f"언어: {doc.language}")

        # 페이지 수
        if doc.page_count:
            parts.append(f"페이지: {doc.page_count}페이지")

        return " | ".join(parts)


# 싱글톤 인스턴스
_db_vector_service = None


async def get_db_vector_service() -> DBVectorService:
    """DB 벡터 서비스 인스턴스 반환"""
    global _db_vector_service
    if _db_vector_service is None:
        _db_vector_service = DBVectorService()
    return _db_vector_service