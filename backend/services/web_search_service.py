import asyncio
import json
from typing import List, Dict, Any, Optional
import httpx
from loguru import logger
from datetime import datetime

from ..config.settings import settings


class WebSearchService:
    """외부 웹 검색을 통한 실시간 정보 수집 서비스"""

    def __init__(self):
        self.client = None
        self.search_engines = {
            "duckduckgo": self._search_duckduckgo,
            "serper": self._search_serper,  # Google Search API 대안
        }
        self.default_engine = "duckduckgo"

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 초기화"""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": "Manufacturing DataSheet RAG System/1.0"
                }
            )
        return self.client

    async def search(
        self,
        query: str,
        max_results: int = 5,
        engine: str = None,
        language: str = "kr"
    ) -> List[Dict[str, Any]]:
        """웹 검색 실행"""
        engine = engine or self.default_engine

        if engine not in self.search_engines:
            raise ValueError(f"지원하지 않는 검색 엔진: {engine}")

        try:
            search_func = self.search_engines[engine]
            results = await search_func(query, max_results, language)

            logger.info(f"웹 검색 완료 ({engine}): '{query}' - {len(results)}개 결과")
            return results

        except Exception as e:
            logger.error(f"웹 검색 실패 ({engine}): {e}")
            return []

    async def _search_duckduckgo(
        self,
        query: str,
        max_results: int,
        language: str
    ) -> List[Dict[str, Any]]:
        """DuckDuckGo Instant Answer API 사용"""
        client = await self._get_client()

        try:
            # DuckDuckGo Instant Answer API
            params = {
                "q": query,
                "format": "json",
                "t": "manufacturing_rag",
                "safesearch": "moderate",
            }

            response = await client.get("https://api.duckduckgo.com/", params=params)
            response.raise_for_status()

            data = response.json()
            results = []

            # Abstract (요약 정보)
            if data.get("Abstract"):
                results.append({
                    "title": data.get("AbstractText", "")[:100] + "..." if len(data.get("AbstractText", "")) > 100 else data.get("AbstractText", ""),
                    "content": data.get("Abstract"),
                    "url": data.get("AbstractURL", ""),
                    "source": data.get("AbstractSource", "DuckDuckGo"),
                    "type": "instant_answer",
                    "relevance_score": 0.9
                })

            # Related Topics
            for topic in data.get("RelatedTopics", [])[:max_results-1]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text", "")[:100] + "..." if len(topic.get("Text", "")) > 100 else topic.get("Text", ""),
                        "content": topic.get("Text", ""),
                        "url": topic.get("FirstURL", ""),
                        "source": "DuckDuckGo Related",
                        "type": "related_topic",
                        "relevance_score": 0.7
                    })

            # Definition
            if data.get("Definition"):
                results.append({
                    "title": "정의",
                    "content": data.get("Definition"),
                    "url": data.get("DefinitionURL", ""),
                    "source": data.get("DefinitionSource", ""),
                    "type": "definition",
                    "relevance_score": 0.8
                })

            # Answer (계산 결과 등)
            if data.get("Answer"):
                results.append({
                    "title": "답변",
                    "content": data.get("Answer"),
                    "url": "",
                    "source": "DuckDuckGo Calculator",
                    "type": "direct_answer",
                    "relevance_score": 0.95
                })

            return results[:max_results]

        except Exception as e:
            logger.error(f"DuckDuckGo 검색 실패: {e}")
            # 대안: 간단한 검색 결과 반환
            return await self._fallback_search(query, max_results)

    async def _search_serper(
        self,
        query: str,
        max_results: int,
        language: str
    ) -> List[Dict[str, Any]]:
        """Serper.dev API 사용 (Google Search API 대안)"""
        # API 키가 필요한 서비스
        api_key = getattr(settings, 'serper_api_key', None)
        if not api_key:
            logger.warning("Serper API 키가 없습니다. DuckDuckGo로 대체합니다.")
            return await self._search_duckduckgo(query, max_results, language)

        client = await self._get_client()

        try:
            headers = {
                "X-API-KEY": api_key,
                "Content-Type": "application/json"
            }

            payload = {
                "q": query,
                "gl": "kr" if language == "kr" else "us",
                "hl": "ko" if language == "kr" else "en",
                "num": max_results
            }

            response = await client.post(
                "https://google.serper.dev/search",
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            results = []

            # Organic results
            for item in data.get("organic", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "content": item.get("snippet", ""),
                    "url": item.get("link", ""),
                    "source": item.get("displayLink", ""),
                    "type": "organic",
                    "relevance_score": 0.8
                })

            # Knowledge graph
            if data.get("knowledgeGraph"):
                kg = data["knowledgeGraph"]
                results.insert(0, {
                    "title": kg.get("title", ""),
                    "content": kg.get("description", ""),
                    "url": kg.get("website", ""),
                    "source": "Google Knowledge Graph",
                    "type": "knowledge_graph",
                    "relevance_score": 0.95
                })

            return results

        except Exception as e:
            logger.error(f"Serper 검색 실패: {e}")
            return await self._fallback_search(query, max_results)

    async def _fallback_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """대체 검색 방법 (실패 시 사용)"""
        return [{
            "title": "검색 제한",
            "content": f"'{query}'에 대한 외부 검색이 현재 제한되어 있습니다. 내부 문서에서만 검색합니다.",
            "url": "",
            "source": "시스템 알림",
            "type": "system_notice",
            "relevance_score": 0.1
        }]

    async def search_manufacturing_specific(
        self,
        query: str,
        max_results: int = 3
    ) -> List[Dict[str, Any]]:
        """제조업 특화 검색"""
        # 제조업 관련 키워드 추가
        manufacturing_terms = [
            "datasheet", "specification", "technical specs",
            "manufacturing", "industrial", "component",
            "DDR5", "memory", "semiconductor"
        ]

        # 질의에 제조업 키워드가 없으면 추가
        enhanced_query = query
        if not any(term.lower() in query.lower() for term in manufacturing_terms):
            enhanced_query = f"{query} manufacturing datasheet specification"

        return await self.search(enhanced_query, max_results)

    async def validate_search_results(
        self,
        results: List[Dict[str, Any]],
        original_query: str
    ) -> List[Dict[str, Any]]:
        """검색 결과 품질 검증 및 필터링"""
        validated_results = []

        for result in results:
            # 기본 품질 검사
            if not result.get("content") or len(result.get("content", "")) < 10:
                continue

            # 관련성 점수 조정
            relevance = result.get("relevance_score", 0.5)

            # 제조업 관련 키워드 보너스
            manufacturing_keywords = [
                "datasheet", "specification", "memory", "DDR", "component",
                "manufacturing", "technical", "industrial", "semiconductor"
            ]

            content_lower = result.get("content", "").lower()
            title_lower = result.get("title", "").lower()

            keyword_bonus = sum(
                0.1 for keyword in manufacturing_keywords
                if keyword in content_lower or keyword in title_lower
            )

            adjusted_relevance = min(1.0, relevance + keyword_bonus)
            result["relevance_score"] = adjusted_relevance

            # 최소 관련성 임계값 적용
            if adjusted_relevance >= 0.3:
                validated_results.append(result)

        # 관련성 순으로 정렬
        validated_results.sort(key=lambda x: x["relevance_score"], reverse=True)

        return validated_results

    async def close(self):
        """리소스 정리"""
        if self.client:
            await self.client.aclose()
            self.client = None


# 싱글톤 인스턴스
_web_search_service = None


async def get_web_search_service() -> WebSearchService:
    """웹 검색 서비스 인스턴스 반환"""
    global _web_search_service
    if _web_search_service is None:
        _web_search_service = WebSearchService()
    return _web_search_service