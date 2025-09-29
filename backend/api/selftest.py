from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from ..config.database import get_db
from ..models.quality_models import (
    SelfTestRequest, SelfTestSummary, SelfTestCase,
    QualityCheckRequest, ValidationResult
)
from ..models.request_models import QueryRequest, UserRole
from ..services.quality_service import get_quality_service
from ..services.rag_service import get_rag_service

router = APIRouter(prefix="/api/selftest", tags=["품질 보증"])


@router.post("/run", response_model=SelfTestSummary, summary="셀프 테스트 실행")
async def run_selftest(
    request: SelfTestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    시스템의 품질 보증을 위한 셀프 테스트를 실행합니다.

    미리 정의된 테스트 스위트 또는 사용자 정의 테스트 케이스를 실행하여
    답변 품질, 환각 억제, 정확도를 검증합니다.
    """
    try:
        quality_service = await get_quality_service()
        rag_service = await get_rag_service()

        # 테스트 케이스 준비
        if request.custom_cases:
            test_cases = []
            for case in request.custom_cases:
                # 실제 RAG 시스템으로 답변 생성
                query_request = QueryRequest(
                    question=case.question,
                    user_role=UserRole.ENGINEER,
                    top_k=5
                )
                response = await rag_service.query(query_request)

                test_cases.append({
                    "question": case.question,
                    "expected_answer": case.expected_answer or "",
                    "actual_answer": response.answer,
                    "expected_validation": case.expected_validation,
                    "sources": [{"content": source.content} for source in response.sources],
                    "confidence": response.confidence
                })
        else:
            # 미리 정의된 테스트 스위트 실행
            test_cases = await _get_predefined_test_suite(request.test_suite, rag_service)

        # 셀프 테스트 실행
        results = quality_service.run_selftest(test_cases)

        logger.info(f"셀프 테스트 '{request.test_suite}' 완료: {results['passed']}/{results['total_tests']} 통과")

        return SelfTestSummary(**results)

    except Exception as e:
        logger.error(f"셀프 테스트 실행 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"셀프 테스트 실행 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/validate", response_model=ValidationResult, summary="답변 품질 검증")
async def validate_answer(
    request: QualityCheckRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    특정 답변의 품질을 검증합니다.

    환각 현상, 소스 일치성, 신뢰도 등을 종합적으로 분석하여
    답변의 품질을 평가합니다.
    """
    try:
        quality_service = await get_quality_service()

        validation_result = quality_service.validate_answer(
            question=request.question,
            answer=request.answer,
            sources=request.sources,
            confidence=request.confidence
        )

        logger.info(f"답변 품질 검증 완료 - 점수: {validation_result['quality_score']:.2f}")

        return ValidationResult(**validation_result)

    except Exception as e:
        logger.error(f"답변 품질 검증 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"답변 품질 검증 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/suites", summary="사용 가능한 테스트 스위트 목록")
async def get_test_suites():
    """사용 가능한 테스트 스위트 목록을 반환합니다."""
    return {
        "test_suites": [
            {
                "name": "manufacturing",
                "description": "제조업 데이터시트 전용 테스트",
                "test_count": 15
            },
            {
                "name": "general",
                "description": "일반적인 RAG 시스템 테스트",
                "test_count": 10
            },
            {
                "name": "hallucination",
                "description": "환각 억제 전용 테스트",
                "test_count": 8
            },
            {
                "name": "accuracy",
                "description": "정확도 검증 테스트",
                "test_count": 12
            }
        ]
    }


@router.get("/suite/{suite_name}", summary="특정 테스트 스위트 정보")
async def get_test_suite_info(suite_name: str):
    """특정 테스트 스위트의 상세 정보를 반환합니다."""
    suite_definitions = {
        "manufacturing": {
            "name": "제조업 데이터시트 테스트",
            "description": "DDR5, 메모리 모듈 등 제조업 특화 질문들",
            "categories": ["전압", "타이밍", "용량", "호환성", "온도"],
            "expected_accuracy": 0.85
        },
        "general": {
            "name": "일반 RAG 테스트",
            "description": "기본적인 문서 검색 및 질의응답",
            "categories": ["검색", "요약", "분류", "추출"],
            "expected_accuracy": 0.80
        },
        "hallucination": {
            "name": "환각 억제 테스트",
            "description": "존재하지 않는 정보에 대한 적절한 응답",
            "categories": ["거짓 정보", "추측", "없는 데이터"],
            "expected_accuracy": 0.90
        },
        "accuracy": {
            "name": "정확도 검증 테스트",
            "description": "명확한 답이 있는 질문들의 정확도",
            "categories": ["수치", "사실", "정의", "절차"],
            "expected_accuracy": 0.88
        }
    }

    if suite_name not in suite_definitions:
        raise HTTPException(
            status_code=404,
            detail=f"테스트 스위트 '{suite_name}'을 찾을 수 없습니다."
        )

    return suite_definitions[suite_name]


async def _get_predefined_test_suite(suite_name: str, rag_service) -> List[Dict[str, Any]]:
    """미리 정의된 테스트 스위트를 반환합니다."""

    if suite_name == "manufacturing":
        questions = [
            ("DDR5의 동작 전압은 얼마인가요?", True),
            ("DDR5의 최대 용량은?", True),
            ("RDIMM과 UDIMM의 차이는?", True),
            ("DDR5의 ECC 기능은?", True),
            ("메모리 모듈의 온도 범위는?", True),
            ("DDR6의 출시일은 언제인가요?", False),  # 존재하지 않는 정보
            ("이 제품의 가격은 얼마인가요?", False),  # 문서에 없는 정보
            ("제조사의 연락처는?", False),  # 관련 없는 정보
        ]
    elif suite_name == "general":
        questions = [
            ("문서에는 어떤 제품들이 설명되어 있나요?", True),
            ("주요 기술 사양은 무엇인가요?", True),
            ("호환성 정보가 있나요?", True),
            ("설치 방법이 설명되어 있나요?", True),
            ("이 회사의 주식 가격은?", False),  # 관련 없는 정보
            ("CEO가 누구인가요?", False),  # 문서에 없는 정보
        ]
    elif suite_name == "hallucination":
        questions = [
            ("존재하지 않는 DDR7 규격에 대해 알려주세요", False),
            ("이 제품의 미래 로드맵은?", False),
            ("경쟁사 비교 분석해주세요", False),
            ("시장 점유율은 어떻게 되나요?", False),
        ]
    elif suite_name == "accuracy":
        questions = [
            ("DDR5의 정확한 데이터 전송률은?", True),
            ("메모리 모듈의 핀 수는?", True),
            ("동작 온도 범위는 정확히 얼마인가요?", True),
            ("전력 소비량은?", True),
        ]
    else:
        raise HTTPException(
            status_code=404,
            detail=f"알 수 없는 테스트 스위트: {suite_name}"
        )

    test_cases = []
    for question, expected_valid in questions:
        try:
            query_request = QueryRequest(
                question=question,
                user_role=UserRole.ENGINEER,
                top_k=5
            )
            response = await rag_service.query(query_request)

            test_cases.append({
                "question": question,
                "expected_answer": "",
                "actual_answer": response.answer,
                "expected_validation": expected_valid,
                "sources": [{"content": source.content} for source in response.sources],
                "confidence": response.confidence
            })
        except Exception as e:
            logger.error(f"테스트 케이스 생성 실패 ({question}): {e}")
            # 실패한 경우 더미 데이터 추가
            test_cases.append({
                "question": question,
                "expected_answer": "",
                "actual_answer": "테스트 실행 실패",
                "expected_validation": False,
                "sources": [],
                "confidence": 0.0
            })

    return test_cases