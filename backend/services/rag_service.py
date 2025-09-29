import time
from typing import List, Dict, Any, Optional
from loguru import logger
from datetime import datetime

from .ollama_service import get_ollama_service
from .vector_service import get_vector_service
from .quality_service import get_quality_service
from ..models.request_models import QueryRequest, UserRole
from ..models.response_models import QueryResponse, SourceInfo
from ..config.database import AsyncSessionLocal, QueryLog, Document


class ManufacturingRAGService:
    """제조업 특화 RAG 서비스"""

    def __init__(self):
        self.role_keywords = {
            UserRole.ENGINEER: [
                "specifications", "parameters", "design", "technical", "electrical",
                "mechanical", "performance", "characteristics", "dimensions"
            ],
            UserRole.QUALITY: [
                "limits", "tolerance", "standards", "compliance", "testing",
                "quality", "certification", "reliability", "durability"
            ],
            UserRole.SALES: [
                "features", "benefits", "advantages", "comparison", "competitive",
                "applications", "use cases", "market", "customer value"
            ],
            UserRole.SUPPORT: [
                "troubleshooting", "compatibility", "solutions", "problems",
                "issues", "installation", "maintenance", "support", "help"
            ]
        }

        self.role_instructions = {
            UserRole.ENGINEER: "기술적 세부사항, 사양, 설계 파라미터에 집중하여 정확한 수치와 조건을 포함해 답변하세요.",
            UserRole.QUALITY: "품질 기준, 한계치, 테스트 조건, 규격 준수 사항에 중점을 두어 답변하세요.",
            UserRole.SALES: "제품의 특징, 장점, 경쟁 우위를 강조하여 고객 가치 중심으로 답변하세요.",
            UserRole.SUPPORT: "문제해결 방법, 호환성 정보, 실용적인 해결책에 초점을 맞춰 답변하세요."
        }

    async def query(self, request: QueryRequest) -> QueryResponse:
        """역할 기반 질의응답"""
        start_time = time.time()

        try:
            # 1. 질문 분석 및 확장
            enhanced_query = self._enhance_query(request.question, request.user_role)
            logger.info(f"원본 질문: {request.question}")
            logger.info(f"확장된 질문: {enhanced_query}")

            # 2. 벡터 검색 (타임아웃 30초)
            vector_service = await get_vector_service()

            import asyncio
            try:
                search_results = await asyncio.wait_for(
                    vector_service.search(
                        query=enhanced_query,
                        top_k=request.top_k,
                        filter_metadata=self._build_metadata_filter(request.document_filter)
                    ),
                    timeout=30.0
                )
                logger.info(f"벡터 검색 완료: {len(search_results)}개 결과")
            except asyncio.TimeoutError:
                logger.error("벡터 검색 타임아웃 (30초)")
                raise Exception("벡터 검색 시간이 초과되었습니다.")

            if not search_results:
                return QueryResponse(
                    answer="죄송합니다. 관련 정보를 찾을 수 없습니다. 다른 키워드로 검색해보시거나 문서가 업로드되었는지 확인해주세요.",
                    confidence=0.0,
                    sources=[],
                    query_time_ms=int((time.time() - start_time) * 1000),
                    model_used="N/A"
                )

            # 3. 문서 메타데이터 보강 및 컨텍스트 구성 (WITH DATABASE TIMEOUT)
            try:
                document_info_map = await asyncio.wait_for(
                    self._fetch_document_info_map(search_results),
                    timeout=10.0  # 10초 타임아웃
                )
                logger.info(f"문서 메타데이터 조회 완료: {len(document_info_map)}개")
            except asyncio.TimeoutError:
                logger.error("문서 메타데이터 조회 타임아웃 (10초) - 기본 메타데이터로 대체")
                document_info_map = {}
            except Exception as e:
                logger.warning(f"문서 메타데이터 조회 실패: {e} - 기본 메타데이터로 대체")
                document_info_map = {}

            context, sources = self._build_context(search_results, request.user_role, document_info_map)

            # 4. LLM 응답 생성 (타임아웃 60초)
            ollama_service = await get_ollama_service()
            prompt = self._create_role_specific_prompt(request.question, context, request.user_role)

            try:
                response_text = await asyncio.wait_for(
                    ollama_service.generate_response(
                        prompt=prompt,
                        context=context,
                        temperature=0.1,
                        max_tokens=512
                    ),
                    timeout=60.0
                )
                logger.info(f"LLM 응답 생성 완료: {len(response_text)} 문자")
            except asyncio.TimeoutError:
                logger.error("LLM 응답 생성 타임아웃 (60초)")
                raise Exception("AI 응답 생성 시간이 초과되었습니다.")

            # 5. 신뢰도 계산
            confidence = self._calculate_confidence(search_results, response_text)

            # 6. 품질 검증 (새로 추가)
            try:
                quality_service = await get_quality_service()
                validation_result = quality_service.validate_answer(
                    question=request.question,
                    answer=response_text,
                    sources=[{"content": source.content} for source in sources],
                    confidence=confidence
                )

                # 품질 검증 결과를 로깅
                logger.info(f"품질 검증 완료 - 점수: {validation_result['quality_score']:.2f}, "
                           f"유효성: {validation_result['is_valid']}")

                # 신뢰도 조정
                confidence = validation_result["confidence_adjusted"]

                # 품질이 매우 낮은 경우 기본 응답으로 대체
                if not validation_result["is_valid"] or validation_result["quality_score"] < 0.3:
                    logger.warning("품질 검증 실패 - 기본 응답으로 대체")
                    response_text = "죄송합니다. 정확한 정보를 찾을 수 없습니다. 다른 키워드로 검색해보시거나 문서 내용을 확인해주세요."
                    confidence = 0.1

            except Exception as e:
                logger.warning(f"품질 검증 실패 (계속 진행): {e}")

            # 7. 응답 구성
            query_response = QueryResponse(
                answer=response_text,
                confidence=confidence,
                sources=sources,
                query_time_ms=int((time.time() - start_time) * 1000),
                model_used=ollama_service.model
            )

            # 7. 쿼리 로그 저장
            await self._log_query(request, query_response)

            return query_response

        except Exception as e:
            # 상세한 오류 정보 로깅
            import traceback
            logger.error(f"RAG 질의 처리 실패 - 질문: {request.question}")
            logger.error(f"오류 유형: {type(e).__name__}")
            logger.error(f"오류 메시지: {str(e)}")
            logger.error(f"스택 트레이스: {traceback.format_exc()}")

            # IMPROVED: 구체적인 오류 분류와 사용자 친화적 메시지
            error_message = "질의 처리 중 오류가 발생했습니다. "

            if "validation error" in str(e).lower():
                error_message += "응답 데이터 형식 오류가 발생했습니다. 관리자에게 문의하세요."
                logger.error(f"VALIDATION ERROR - 데이터 모델 검증 실패: {e}")
            elif "connection" in str(e).lower():
                error_message += "서비스 연결에 문제가 있습니다. 잠시 후 다시 시도해주세요."
            elif "timeout" in str(e).lower():
                error_message += "응답 시간이 초과되었습니다. 더 구체적인 질문으로 다시 시도해주세요."
            elif "model" in str(e).lower() or "load" in str(e).lower():
                error_message += "AI 모델 로드 중입니다. 잠시 후 다시 시도해주세요."
            elif "datatype mismatch" in str(e).lower():
                error_message += "데이터 형식 오류가 발생했습니다. 관리자에게 문의하세요."
                logger.error(f"DATABASE ERROR - 데이터타입 불일치: {e}")
            elif "'dict' object is not callable" in str(e):
                error_message += "서비스 초기화 중입니다. 잠시 후 다시 시도해주세요."
                logger.error(f"SERVICE INITIALIZATION ERROR - 서비스 준비 미완료: {e}")
            else:
                error_message += f"관리자에게 문의하거나 잠시 후 다시 시도해주세요. (오류코드: {type(e).__name__})"

            return QueryResponse(
                answer=error_message,
                confidence=0.0,
                sources=[],
                query_time_ms=int((time.time() - start_time) * 1000),
                model_used="error"
            )

    def _enhance_query(self, query: str, role: UserRole) -> str:
        """사용자 역할에 따른 질의 확장"""
        role_specific_keywords = self.role_keywords.get(role, [])

        # 질의에 이미 역할별 키워드가 포함되어 있는지 확인
        query_lower = query.lower()
        matching_keywords = [kw for kw in role_specific_keywords
                           if kw.lower() in query_lower or kw in query_lower]

        # 역할별 키워드가 부족한 경우 보강
        if len(matching_keywords) < 2 and role_specific_keywords:
            enhancement_keywords = role_specific_keywords[:2]
            enhanced_query = f"{query} {' '.join(enhancement_keywords)}"
        else:
            enhanced_query = query

        return enhanced_query

    def _build_metadata_filter(self, document_filter: Optional[str]) -> Dict[str, Any]:
        """문서 필터 구성"""
        if not document_filter:
            return {}

        filters = {}

        # 파일 확장자 필터
        if document_filter.endswith(('.pdf', '.doc', '.docx', '.txt')):
            filters['file_type'] = document_filter.split('.')[-1]
        # 제품군 필터
        elif document_filter:
            filters['product_family'] = document_filter

        return filters

    def _build_context(self, search_results: List[Dict[str, Any]],
                      role: UserRole,
                      document_info_map: Dict[str, Document]) -> tuple[str, List[SourceInfo]]:
        """검색 결과를 컨텍스트와 출처 정보로 변환"""
        context_parts = []
        sources = []

        for i, result in enumerate(search_results):
            content = result.get("page_content", "")
            metadata = result.get("metadata", {})
            score = result.get("score", 0.0)

            if not content.strip():
                continue

            # 문서 정보 보강
            document_id = metadata.get("document_id")
            doc_info = document_info_map.get(document_id) if document_id else None

            # 컨텍스트 생성 (역할별 최적화)
            context_header = f"\n--- 문서 {i+1} ---"
            if doc_info:
                context_header += f"\n파일: {doc_info.filename}"
                if doc_info.product_model:
                    context_header += f"\n제품: {doc_info.product_model}"
                if metadata.get("page"):
                    context_header += f"\n페이지: {metadata.get('page')}"
                if metadata.get("section"):
                    context_header += f"\n섹션: {metadata.get('section')}"

            context_part = f"{context_header}\n내용:\n{content}\n"
            context_parts.append(context_part)

            # 출처 정보 생성 (IMPROVED: Pydantic 길이 제한 준수)
            try:
                # FIXED: content_preview 길이 제한 (max 500자)
                content_preview = content[:500] if len(content) > 500 else content

                source_info = SourceInfo(
                    document_id=str(document_id) if document_id else f"doc_{i}",
                    filename=doc_info.filename if doc_info else metadata.get("source", "Unknown"),
                    content_preview=content_preview,  # 길이 제한 적용
                    page_number=metadata.get("page"),
                    section=metadata.get("section"),
                    relevance_score=float(score)
                )
                sources.append(source_info)
            except Exception as e:
                logger.warning(f"SourceInfo 생성 실패 (인덱스 {i}): {e}")
                # 기본 정보로 fallback
                try:
                    fallback_source = SourceInfo(
                        document_id=f"doc_{i}",
                        filename="Unknown",
                        content_preview=content[:200],  # 더 짧게 제한
                        page_number=metadata.get("page"),
                        section=metadata.get("section"),
                        relevance_score=float(score) if score else 0.0
                    )
                    sources.append(fallback_source)
                except Exception as fallback_e:
                    logger.error(f"Fallback SourceInfo 생성도 실패: {fallback_e}")
                    continue

        # 역할별 컨텍스트 최적화
        context = self._optimize_context_for_role("\n".join(context_parts), role)

        return context, sources

    async def _fetch_document_info_map(
        self,
        search_results: List[Dict[str, Any]]
    ) -> Dict[str, Document]:
        """검색 결과의 문서 메타데이터를 보강 - IMPROVED with connection management"""
        document_ids = set()

        for result in search_results:
            metadata = result.get("metadata") or {}
            document_id = metadata.get("document_id")
            if document_id:
                document_ids.add(str(document_id))

        if not document_ids:
            logger.info("문서 ID가 없어 메타데이터 조회를 건너뜁니다.")
            return {}

        try:
            from sqlalchemy import select
            import asyncio

            logger.info(f"문서 메타데이터 조회 시작: {len(document_ids)}개 ID")

            # CRITICAL FIX: 연결 타임아웃 설정
            async def fetch_with_timeout():
                async with AsyncSessionLocal() as session:
                    # IMPROVED: 쿼리 최적화 및 타임아웃 설정
                    query = select(Document).where(Document.id.in_(document_ids))

                    # 짧은 타임아웃으로 쿼리 실행
                    db_result = await asyncio.wait_for(
                        session.execute(query),
                        timeout=5.0  # 5초 쿼리 타임아웃
                    )
                    documents = db_result.scalars().all()

                    logger.info(f"데이터베이스에서 {len(documents)}개 문서 정보 조회 완료")
                    return {document.id: document for document in documents}

            return await fetch_with_timeout()

        except asyncio.TimeoutError:
            logger.error("데이터베이스 쿼리 타임아웃 - 빈 맵 반환")
            return {}
        except Exception as e:
            logger.warning(f"문서 메타데이터 조회 실패: {e}")
            return {}

    def _optimize_context_for_role(self, context: str, role: UserRole) -> str:
        """역할별 컨텍스트 최적화"""
        # 역할에 따라 관련성 높은 부분을 강조하거나 필터링
        # 현재는 기본 컨텍스트 반환, 향후 NLP 기법으로 개선 가능

        # 컨텍스트 길이 제한
        max_context_length = 3000
        if len(context) > max_context_length:
            context = context[:max_context_length] + "\n[내용이 길어 일부만 표시됨]"

        return context

    def _create_role_specific_prompt(self, question: str, context: str, role: UserRole) -> str:
        """역할별 특화 프롬프트 생성"""
        role_instruction = self.role_instructions.get(role, "")

        prompt = f"""
다음은 제품 데이터시트에서 추출한 기술 정보입니다:

{context}

사용자 역할: {role.value}
지침: {role_instruction}

질문: {question}

위 정보를 바탕으로 정확하고 구체적인 한글 답변을 제공하세요.

** 중요한 답변 형식 지침 **:
1. 반드시 한국어로만 답변하세요
2. 개조식으로 답변하세요 (예: "• DDR5 동작 전압: 1.1V", "• 온도 범위: 0~95℃")
3. 구체적인 수치와 단위를 포함하세요
4. 관련 조건이나 제약사항을 명시하세요
5. 정보가 불충분한 경우 그 사실을 명시하세요
6. 추측하지 말고 제공된 정보에만 기반하여 답변하세요
7. 영어 단어는 필요한 기술용어만 사용하고 괄호로 병기하세요

한글 개조식 답변:"""

        return prompt

    def _calculate_confidence(self, search_results: List[Dict[str, Any]], response: str) -> float:
        """응답 신뢰도 계산 - FAISS 거리 점수를 0-1 범위로 정규화"""
        if not search_results:
            return 0.0

        # FAISS 거리 점수를 유사도 점수로 변환 (거리가 클수록 유사도는 낮음)
        scores = []
        for result in search_results:
            distance = result.get("score", 0.0)
            # 거리 점수를 유사도로 변환: 1 / (1 + distance)
            # 거리 0 → 유사도 1.0, 거리가 클수록 유사도는 0에 근접
            similarity = 1.0 / (1.0 + distance)
            scores.append(similarity)

        avg_similarity = sum(scores) / len(scores) if scores else 0.0

        # 응답 길이 고려 (짧은 응답은 신뢰도 감점)
        response_length_factor = min(len(response) / 100, 1.0)

        # 최종 신뢰도 계산 (0-1 범위 보장)
        confidence = (avg_similarity * 0.7 + response_length_factor * 0.3)

        # 0-1 범위 확실히 보장
        confidence = max(0.0, min(1.0, confidence))

        return round(confidence, 3)

    async def _log_query(self, request: QueryRequest, response: QueryResponse):
        """쿼리 로그 저장"""
        try:
            # IMPROVED: 로그 저장도 타임아웃 적용
            import asyncio

            async def save_log():
                async with AsyncSessionLocal() as session:
                    query_log = QueryLog(
                        question=request.question,
                        user_role=request.user_role.value,
                        answer=response.answer,
                        confidence=response.confidence,
                        query_time_ms=response.query_time_ms,
                        model_used=response.model_used,
                        source_count=len(response.sources),
                        timestamp=datetime.utcnow()
                    )

                    session.add(query_log)
                    await session.commit()
                    logger.info("쿼리 로그 저장 완료")

            # 로그 저장 타임아웃 5초
            await asyncio.wait_for(save_log(), timeout=5.0)

        except asyncio.TimeoutError:
            logger.warning("쿼리 로그 저장 타임아웃")
        except Exception as e:
            logger.warning(f"쿼리 로그 저장 실패: {e}")


# 싱글톤 인스턴스
_rag_service_instance = None

async def get_rag_service() -> ManufacturingRAGService:
    """RAG 서비스 인스턴스 반환"""
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = ManufacturingRAGService()
    return _rag_service_instance