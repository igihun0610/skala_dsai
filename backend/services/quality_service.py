import re
import time
from typing import Dict, List, Optional, Tuple, Any
from loguru import logger
from datetime import datetime

from ..models.request_models import QueryRequest, UserRole
from ..models.response_models import QueryResponse


class QualityAssuranceService:
    """답변 품질 검증 서비스"""

    def __init__(self):
        self.boilerplate_patterns = [
            r"도와드릴 수 있", r"어떻게.*도와", r"무엇.*원하시",
            r"As an AI", r"I'm an AI", r"assist you",
            r"죄송합니다.*도와드리지", r"더 구체적으로.*말씀해"
        ]

        self.hallucination_indicators = [
            r"확실하지.*않지만", r"추측.*입니다", r"아마도",
            r"것 같습니다", r"생각됩니다", r"추정.*됩니다"
        ]

        self.confidence_keywords = {
            "high": ["정확히", "명시되어", "문서에 따르면", "사양서에서"],
            "medium": ["일반적으로", "보통", "대체로"],
            "low": ["가능성이", "추정", "예상", "것으로 보임"]
        }

    def validate_answer(self,
                       question: str,
                       answer: str,
                       sources: List[Dict],
                       confidence: float) -> Dict[str, Any]:
        """답변의 품질을 종합적으로 검증"""

        validation_result = {
            "is_valid": True,
            "quality_score": 0.0,
            "issues": [],
            "suggestions": [],
            "confidence_adjusted": confidence,
            "validation_details": {}
        }

        # 1. 기본적인 답변 유효성 검사
        basic_validation = self._validate_basic_answer(answer)
        validation_result["validation_details"]["basic"] = basic_validation

        if not basic_validation["is_valid"]:
            validation_result["is_valid"] = False
            validation_result["issues"].extend(basic_validation["issues"])

        # 2. 환각 현상 검사
        hallucination_check = self._check_hallucination(answer)
        validation_result["validation_details"]["hallucination"] = hallucination_check

        if hallucination_check["risk_level"] == "high":
            validation_result["confidence_adjusted"] *= 0.5
            validation_result["issues"].append("높은 환각 위험 감지")

        # 3. 소스 일치성 검사
        source_validation = self._validate_source_consistency(answer, sources)
        validation_result["validation_details"]["source_consistency"] = source_validation

        if not source_validation["is_consistent"]:
            validation_result["confidence_adjusted"] *= 0.7
            validation_result["issues"].append("소스와의 일치성 부족")

        # 4. 신뢰도 키워드 분석
        confidence_analysis = self._analyze_confidence_keywords(answer)
        validation_result["validation_details"]["confidence_keywords"] = confidence_analysis

        # 5. 종합 품질 점수 계산
        validation_result["quality_score"] = self._calculate_quality_score(
            basic_validation, hallucination_check, source_validation, confidence_analysis
        )

        # 6. 개선 제안 생성
        validation_result["suggestions"] = self._generate_suggestions(validation_result)

        return validation_result

    def _validate_basic_answer(self, answer: str) -> Dict[str, Any]:
        """기본적인 답변 유효성 검사"""
        result = {
            "is_valid": True,
            "issues": [],
            "checks": {}
        }

        # 빈 답변 검사
        if not answer or len(answer.strip()) < 5:
            result["is_valid"] = False
            result["issues"].append("답변이 너무 짧거나 비어있음")
            result["checks"]["length"] = False
        else:
            result["checks"]["length"] = True

        # N/A 검사
        if answer.strip().upper() == "N/A":
            result["is_valid"] = False
            result["issues"].append("정보를 찾을 수 없음")
            result["checks"]["not_na"] = False
        else:
            result["checks"]["not_na"] = True

        # 보일러플레이트 검사
        is_boilerplate = any(
            re.search(pattern, answer, re.IGNORECASE)
            for pattern in self.boilerplate_patterns
        )

        if is_boilerplate:
            result["is_valid"] = False
            result["issues"].append("일반적인 AI 응답 템플릿 감지")
            result["checks"]["not_boilerplate"] = False
        else:
            result["checks"]["not_boilerplate"] = True

        return result

    def _check_hallucination(self, answer: str) -> Dict[str, Any]:
        """환각 현상 위험도 검사"""
        result = {
            "risk_level": "low",
            "indicators_found": [],
            "risk_score": 0.0
        }

        for pattern in self.hallucination_indicators:
            if re.search(pattern, answer, re.IGNORECASE):
                result["indicators_found"].append(pattern)
                result["risk_score"] += 0.2

        # 위험도 레벨 결정
        if result["risk_score"] >= 0.6:
            result["risk_level"] = "high"
        elif result["risk_score"] >= 0.3:
            result["risk_level"] = "medium"
        else:
            result["risk_level"] = "low"

        return result

    def _validate_source_consistency(self, answer: str, sources: List[Dict]) -> Dict[str, Any]:
        """답변과 소스 문서의 일치성 검사"""
        result = {
            "is_consistent": True,
            "consistency_score": 1.0,
            "source_coverage": 0.0
        }

        if not sources:
            result["is_consistent"] = False
            result["consistency_score"] = 0.0
            return result

        # 답변에서 주요 키워드 추출
        answer_keywords = set(re.findall(r'\b\w{3,}\b', answer.lower()))

        # 소스에서 키워드 매칭 검사
        source_keywords = set()
        for source in sources:
            if 'content' in source:
                source_keywords.update(
                    re.findall(r'\b\w{3,}\b', source['content'].lower())
                )

        if answer_keywords and source_keywords:
            overlap = len(answer_keywords.intersection(source_keywords))
            result["source_coverage"] = overlap / len(answer_keywords)

            if result["source_coverage"] < 0.3:
                result["is_consistent"] = False
                result["consistency_score"] = result["source_coverage"]

        return result

    def _analyze_confidence_keywords(self, answer: str) -> Dict[str, Any]:
        """신뢰도 키워드 분석"""
        result = {
            "confidence_level": "medium",
            "keywords_found": {"high": [], "medium": [], "low": []}
        }

        for level, keywords in self.confidence_keywords.items():
            for keyword in keywords:
                if keyword in answer:
                    result["keywords_found"][level].append(keyword)

        # 신뢰도 레벨 결정
        if result["keywords_found"]["high"]:
            result["confidence_level"] = "high"
        elif result["keywords_found"]["low"]:
            result["confidence_level"] = "low"
        else:
            result["confidence_level"] = "medium"

        return result

    def _calculate_quality_score(self,
                                basic: Dict,
                                hallucination: Dict,
                                source: Dict,
                                confidence: Dict) -> float:
        """종합 품질 점수 계산"""
        score = 0.0

        # 기본 유효성 (40%)
        if basic["is_valid"]:
            score += 0.4

        # 환각 위험도 (30%)
        hallucination_score = {
            "low": 0.3,
            "medium": 0.15,
            "high": 0.0
        }
        score += hallucination_score.get(hallucination["risk_level"], 0.0)

        # 소스 일치성 (20%)
        score += 0.2 * source["consistency_score"]

        # 신뢰도 키워드 (10%)
        confidence_score = {
            "high": 0.1,
            "medium": 0.05,
            "low": 0.0
        }
        score += confidence_score.get(confidence["confidence_level"], 0.0)

        return min(1.0, score)

    def _generate_suggestions(self, validation_result: Dict[str, Any]) -> List[str]:
        """개선 제안 생성"""
        suggestions = []

        if validation_result["quality_score"] < 0.5:
            suggestions.append("답변 품질이 낮습니다. 더 구체적인 정보가 필요합니다.")

        if validation_result["validation_details"]["hallucination"]["risk_level"] == "high":
            suggestions.append("추측성 표현을 줄이고 확실한 정보만 제공하세요.")

        if not validation_result["validation_details"]["source_consistency"]["is_consistent"]:
            suggestions.append("소스 문서의 내용을 더 정확히 반영하세요.")

        if validation_result["confidence_adjusted"] < 0.5:
            suggestions.append("신뢰도가 낮습니다. 더 정확한 소스가 필요합니다.")

        return suggestions

    def run_selftest(self, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """셀프 테스트 실행"""
        results = {
            "total_tests": len(test_cases),
            "passed": 0,
            "failed": 0,
            "test_results": [],
            "overall_score": 0.0,
            "timestamp": datetime.now().isoformat()
        }

        for i, test_case in enumerate(test_cases):
            test_result = {
                "test_id": i + 1,
                "question": test_case.get("question", ""),
                "expected_answer": test_case.get("expected_answer", ""),
                "actual_answer": test_case.get("actual_answer", ""),
                "expected_validation": test_case.get("expected_validation", True),
                "passed": False,
                "validation_result": None
            }

            # 답변 품질 검증
            validation = self.validate_answer(
                test_case.get("question", ""),
                test_case.get("actual_answer", ""),
                test_case.get("sources", []),
                test_case.get("confidence", 0.5)
            )

            test_result["validation_result"] = validation

            # 테스트 통과 여부 판단
            if test_case.get("expected_validation", True):
                # 유효한 답변을 기대하는 경우
                test_result["passed"] = validation["is_valid"] and validation["quality_score"] >= 0.5
            else:
                # 무효한 답변을 기대하는 경우 (예: "정보 없음")
                test_result["passed"] = not validation["is_valid"] or validation["quality_score"] < 0.5

            if test_result["passed"]:
                results["passed"] += 1
            else:
                results["failed"] += 1

            results["test_results"].append(test_result)

        results["overall_score"] = results["passed"] / results["total_tests"] if results["total_tests"] > 0 else 0.0

        logger.info(f"셀프 테스트 완료: {results['passed']}/{results['total_tests']} 통과")

        return results


# 전역 인스턴스
_quality_service_instance: Optional[QualityAssuranceService] = None


async def get_quality_service() -> QualityAssuranceService:
    """품질 보증 서비스 인스턴스 반환"""
    global _quality_service_instance
    if _quality_service_instance is None:
        _quality_service_instance = QualityAssuranceService()
    return _quality_service_instance