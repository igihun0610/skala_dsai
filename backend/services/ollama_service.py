import asyncio
import httpx
import json
from typing import Optional, Dict, Any, List
from loguru import logger
from ..config.settings import settings

class OllamaService:
    """Ollama 로컬 LLM 서비스"""

    def __init__(self, host: str = None, model: str = None, timeout: int = None):
        self.host = host or settings.ollama_host
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def is_available(self) -> bool:
        """Ollama 서버 상태 확인"""
        try:
            response = await self.client.get(f"{self.host}/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama 서버 연결 실패: {e}")
            return False

    async def list_models(self) -> List[str]:
        """사용 가능한 모델 목록 조회"""
        try:
            response = await self.client.get(f"{self.host}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except Exception as e:
            logger.error(f"모델 목록 조회 실패: {e}")
            return []

    async def pull_model(self, model_name: str) -> bool:
        """모델 다운로드"""
        try:
            payload = {"name": model_name}
            async with self.client.stream("POST", f"{self.host}/api/pull", json=payload) as response:
                if response.status_code == 200:
                    async for line in response.aiter_lines():
                        if line:
                            progress = json.loads(line)
                            if progress.get("status") == "success":
                                logger.info(f"모델 {model_name} 다운로드 완료")
                                return True
                            elif "error" in progress:
                                logger.error(f"모델 다운로드 오류: {progress['error']}")
                                return False
        except Exception as e:
            logger.error(f"모델 다운로드 실패: {e}")
            return False

    async def generate_response(self, prompt: str, context: str = "", **kwargs) -> str:
        """컨텍스트 기반 응답 생성"""
        try:
            formatted_prompt = self._format_manufacturing_prompt(prompt, context)

            payload = {
                "model": self.model,
                "prompt": formatted_prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", settings.temperature),
                    "top_k": kwargs.get("top_k", 40),
                    "top_p": kwargs.get("top_p", 0.9),
                    "num_predict": kwargs.get("max_tokens", 512),
                }
            }

            response = await self.client.post(f"{self.host}/api/generate", json=payload)

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                logger.error(f"Ollama API 오류: {response.status_code} - {response.text}")
                return "죄송합니다. 현재 응답을 생성할 수 없습니다."

        except Exception as e:
            logger.error(f"응답 생성 실패: {e}")
            return "죄송합니다. 시스템 오류가 발생했습니다."

    async def generate_streaming_response(self, prompt: str, context: str = "", **kwargs):
        """스트리밍 응답 생성"""
        try:
            formatted_prompt = self._format_manufacturing_prompt(prompt, context)

            payload = {
                "model": self.model,
                "prompt": formatted_prompt,
                "stream": True,
                "options": {
                    "temperature": kwargs.get("temperature", settings.temperature),
                    "top_k": kwargs.get("top_k", 40),
                    "top_p": kwargs.get("top_p", 0.9),
                    "num_predict": kwargs.get("max_tokens", 512),
                }
            }

            async with self.client.stream("POST", f"{self.host}/api/generate", json=payload) as response:
                if response.status_code == 200:
                    async for line in response.aiter_lines():
                        if line:
                            chunk = json.loads(line)
                            if chunk.get("response"):
                                yield chunk["response"]
                            if chunk.get("done"):
                                break
                else:
                    logger.error(f"스트리밍 API 오류: {response.status_code}")
                    yield "죄송합니다. 현재 응답을 생성할 수 없습니다."

        except Exception as e:
            logger.error(f"스트리밍 응답 생성 실패: {e}")
            yield "죄송합니다. 시스템 오류가 발생했습니다."

    def _format_manufacturing_prompt(self, question: str, context: str) -> str:
        """제조업 특화 프롬프트 템플릿"""
        if not context.strip():
            return f"""
다음 질문에 대해 간결하고 정확하게 답변해주세요:

질문: {question}

답변:"""

        return f"""
다음은 제품 데이터시트에서 추출한 기술 정보입니다:

{context}

질문: {question}

위 정보를 바탕으로 정확하고 구체적인 답변을 제공하세요.
답변에는 다음을 포함해주세요:
1. 구체적인 수치와 단위 (있는 경우)
2. 관련 조건이나 제약사항
3. 정보가 불충분한 경우 그 사실을 명시

답변:"""

    def _format_role_specific_prompt(self, question: str, context: str, role: str) -> str:
        """사용자 역할별 특화 프롬프트"""
        role_instructions = {
            "engineer": "기술적 세부사항과 사양에 집중하여 답변해주세요.",
            "quality": "품질 기준, 한계치, 테스트 조건에 중점을 두어 답변해주세요.",
            "sales": "제품의 특징과 장점을 강조하여 답변해주세요.",
            "support": "문제해결과 호환성 정보에 초점을 맞춰 답변해주세요."
        }

        instruction = role_instructions.get(role, "")
        base_prompt = self._format_manufacturing_prompt(question, context)

        if instruction:
            return base_prompt.replace("답변:", f"{instruction}\n\n답변:")

        return base_prompt

    async def check_model_exists(self, model_name: str = None) -> bool:
        """특정 모델의 존재 여부 확인"""
        model_name = model_name or self.model
        models = await self.list_models()
        return any(model_name in model for model in models)

    async def ensure_model_available(self) -> bool:
        """모델 사용 가능 상태 보장 (없으면 다운로드)"""
        if not await self.is_available():
            logger.error("Ollama 서버에 연결할 수 없습니다.")
            return False

        if not await self.check_model_exists():
            logger.info(f"모델 {self.model}을 다운로드합니다...")
            return await self.pull_model(self.model)

        return True

# Global Ollama service instance
_ollama_service: Optional[OllamaService] = None

async def get_ollama_service() -> OllamaService:
    """Ollama 서비스 싱글톤 인스턴스 반환"""
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaService()
        # 모델 사용 가능성 확인
        await _ollama_service.ensure_model_available()
    return _ollama_service