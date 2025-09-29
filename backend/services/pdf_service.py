import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor
from loguru import logger

try:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
except ImportError:
    logger.warning("pypdf not installed. PDF parsing will not work.")
    PdfReader = None

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document

from ..config.settings import settings
from ..config.database import AsyncSessionLocal, Document as DocumentModel


class PDFParsingService:
    """PDF 파싱 및 텍스트 추출 서비스"""

    def __init__(self):
        self.chunk_size = settings.chunk_size
        self.chunk_overlap = settings.chunk_overlap
        self.upload_path = Path(settings.upload_path)
        self.processed_path = Path(settings.processed_path)
        self.executor = ThreadPoolExecutor(max_workers=2)

        # 디렉토리 생성
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.processed_path.mkdir(parents=True, exist_ok=True)

    async def save_uploaded_file(self, file_content: bytes, filename: str) -> str:
        """업로드된 파일 저장"""
        try:
            # 파일명 해시 생성 (중복 방지)
            file_hash = hashlib.md5(file_content).hexdigest()
            safe_filename = f"{file_hash}_{filename}"
            file_path = self.upload_path / safe_filename

            # 파일 저장
            with open(file_path, "wb") as f:
                f.write(file_content)

            logger.info(f"파일 저장 완료: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"파일 저장 실패 ({filename}): {e}")
            raise

    async def extract_text_from_pdf(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """PDF에서 텍스트 추출"""
        if not PdfReader:
            raise ImportError("pypdf 라이브러리가 설치되지 않았습니다.")

        try:
            # 비동기적으로 PDF 읽기
            text, metadata = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._extract_text_sync, file_path
            )
            return text, metadata

        except Exception as e:
            logger.error(f"PDF 텍스트 추출 실패 ({file_path}): {e}")
            raise

    def _extract_text_sync(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """동기적 PDF 텍스트 추출 (내부 함수)"""
        try:
            reader = PdfReader(file_path)

            # 메타데이터 추출
            metadata = {
                "page_count": len(reader.pages),
                "title": reader.metadata.get("/Title", ""),
                "author": reader.metadata.get("/Author", ""),
                "subject": reader.metadata.get("/Subject", ""),
                "creator": reader.metadata.get("/Creator", ""),
                "producer": reader.metadata.get("/Producer", ""),
                "creation_date": reader.metadata.get("/CreationDate", ""),
                "modification_date": reader.metadata.get("/ModDate", ""),
            }

            # 전체 텍스트 추출
            full_text = ""
            page_texts = []

            for i, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():
                        # 텍스트 정규화
                        normalized_text = self._normalize_text(page_text)
                        page_texts.append({
                            "page": i + 1,
                            "text": normalized_text,
                            "raw_text": page_text
                        })
                        full_text += f"\n\n--- Page {i + 1} ---\n{normalized_text}"

                except Exception as e:
                    logger.warning(f"페이지 {i + 1} 텍스트 추출 실패: {e}")
                    continue

            metadata["pages"] = page_texts
            metadata["total_characters"] = len(full_text)

            if not full_text.strip():
                raise ValueError("PDF에서 텍스트를 추출할 수 없습니다. 스캔된 문서일 가능성이 있습니다.")

            return full_text.strip(), metadata

        except PdfReadError as e:
            raise ValueError(f"PDF 파일이 손상되었거나 읽을 수 없습니다: {e}")
        except Exception as e:
            raise RuntimeError(f"PDF 처리 중 오류 발생: {e}")

    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화"""
        if not text:
            return ""

        # 리가처 문자 변환
        ligature_map = {
            "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
            "\ufb03": "ffi", "\ufb04": "ffl"
        }

        for ligature, replacement in ligature_map.items():
            text = text.replace(ligature, replacement)

        # 하이픈 연결된 단어 처리 (줄바꿈으로 분리된 단어 연결)
        import re
        text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)

        # 다중 공백을 단일 공백으로
        text = re.sub(r"\s+", " ", text)

        # 다중 줄바꿈을 단일 줄바꿈으로
        text = re.sub(r"\n+", "\n", text)

        return text.strip()

    async def chunk_text(
        self,
        text: str,
        document_id: str = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """텍스트를 청크로 분할"""
        try:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]
            )

            loop = asyncio.get_event_loop()

            # 문서별 공통 메타데이터 구성
            common_metadata: Dict[str, Any] = {}
            if document_id:
                common_metadata["document_id"] = document_id

            # 문서 정보를 데이터베이스에서 가져오기
            document_info = None
            if document_id:
                try:
                    from ..config.database import AsyncSessionLocal
                    from ..config.database import Document as DBDocument
                    from sqlalchemy import select

                    async with AsyncSessionLocal() as db:
                        result = await db.execute(select(DBDocument).where(DBDocument.id == document_id))
                        document_info = result.scalar_one_or_none()
                except Exception as e:
                    logger.warning(f"문서 정보 조회 실패: {e}")

            if document_info:
                if document_info.original_name:
                    common_metadata["filename"] = document_info.original_name
                if document_info.document_type:
                    common_metadata["document_type"] = document_info.document_type
                if document_info.product_family:
                    common_metadata["product_family"] = document_info.product_family
                if document_info.product_model:
                    common_metadata["product_model"] = document_info.product_model

            page_entries = []
            if metadata and metadata.get("pages"):
                page_entries = [page for page in metadata["pages"] if page.get("text")]

            if page_entries:
                texts: List[str] = []
                metadatas: List[Dict[str, Any]] = []

                for page in page_entries:
                    base_metadata = dict(common_metadata)
                    if page.get("page") is not None:
                        base_metadata["page_number"] = int(page.get("page"))
                    texts.append(page.get("text", ""))
                    metadatas.append(base_metadata)

                def create_documents_with_metadata():
                    return splitter.create_documents(texts, metadatas=metadatas)

                chunks = await loop.run_in_executor(
                    self.executor,
                    create_documents_with_metadata
                )
            else:
                base_metadata = dict(common_metadata)

                def create_single_document():
                    return splitter.create_documents([text], metadatas=[base_metadata])

                chunks = await loop.run_in_executor(
                    self.executor,
                    create_single_document
                )

            # 청크에 메타데이터 추가
            for i, chunk in enumerate(chunks):
                chunk.metadata.setdefault("document_id", document_id)
                if document_info:
                    if document_info.original_name:
                        chunk.metadata.setdefault("filename", document_info.original_name)
                    if document_info.document_type:
                        chunk.metadata.setdefault("document_type", document_info.document_type)
                    if document_info.product_family:
                        chunk.metadata.setdefault("product_family", document_info.product_family)
                    if document_info.product_model:
                        chunk.metadata.setdefault("product_model", document_info.product_model)

                chunk.metadata["chunk_index"] = i
                chunk.metadata["chunk_size"] = len(chunk.page_content)
                if "page_number" in chunk.metadata and chunk.metadata["page_number"] is not None:
                    try:
                        chunk.metadata["page_number"] = int(chunk.metadata["page_number"])
                    except (TypeError, ValueError):
                        chunk.metadata["page_number"] = None

            logger.info(f"텍스트를 {len(chunks)}개 청크로 분할 완료")
            return chunks

        except Exception as e:
            logger.error(f"텍스트 청킹 실패: {e}")
            raise

    async def process_pdf_file(self, file_path: str, document_id: str) -> Tuple[List[Document], Dict[str, Any]]:
        """PDF 파일 전체 처리 파이프라인"""
        try:
            # 1. 텍스트 추출
            logger.info(f"PDF 텍스트 추출 시작: {file_path}")
            text, metadata = await self.extract_text_from_pdf(file_path)

            # 2. 텍스트 청킹
            logger.info(f"텍스트 청킹 시작")
            chunks = await self.chunk_text(text, document_id, metadata)

            # 3. 처리된 텍스트 저장 (옵션)
            processed_file_path = self.processed_path / f"{document_id}.txt"
            with open(processed_file_path, "w", encoding="utf-8") as f:
                f.write(text)

            logger.info(f"PDF 처리 완료: {len(chunks)}개 청크 생성")

            return chunks, metadata

        except Exception as e:
            logger.error(f"PDF 처리 실패 ({file_path}): {e}")
            raise

    async def extract_tables_from_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """PDF에서 테이블 추출 (향후 확장용)"""
        # TODO: pdfplumber나 tabula-py를 사용한 테이블 추출 구현
        logger.warning("테이블 추출 기능은 아직 구현되지 않았습니다.")
        return []

    async def detect_document_structure(self, text: str) -> Dict[str, Any]:
        """문서 구조 감지 (섹션, 제목 등)"""
        # TODO: 정규식이나 ML 모델을 사용한 구조 감지
        import re

        # 간단한 섹션 감지
        sections = []
        section_patterns = [
            r"^\s*(\d+\.?\s*.+?)$",  # 숫자로 시작하는 제목
            r"^\s*([A-Z][^a-z\n]{10,})$",  # 대문자 제목
            r"^\s*(Introduction|Abstract|Conclusion|References?|Specification|Features?|Overview).*$",
        ]

        for pattern in section_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                sections.append({
                    "title": match.group(1).strip(),
                    "start_pos": match.start(),
                    "pattern": pattern
                })

        return {
            "sections": sections,
            "has_toc": "table of contents" in text.lower() or "목차" in text,
            "has_index": "index" in text.lower() or "색인" in text,
        }

    def cleanup_temp_files(self, older_than_hours: int = 24):
        """임시 파일 정리"""
        import time

        try:
            now = time.time()
            cutoff = older_than_hours * 3600

            for file_path in self.processed_path.glob("*.txt"):
                if now - file_path.stat().st_mtime > cutoff:
                    file_path.unlink()
                    logger.info(f"임시 파일 삭제: {file_path}")

        except Exception as e:
            logger.error(f"임시 파일 정리 실패: {e}")

    async def process_pdf_background(self, file_path: str, document_id: str, vector_service):
        """백그라운드에서 PDF 처리 및 벡터화 - 논블로킹 처리"""
        try:
            # 처리 상태를 processing으로 업데이트
            await self._update_document_status(document_id, "processing")

            # PDF 처리
            logger.info(f"🔄 백그라운드 PDF 처리 시작: {document_id}")
            chunks, metadata = await self.process_pdf_file(file_path, document_id)

            # chunks는 이미 LangChain Document 객체들이므로 바로 사용
            documents = chunks

            # 벡터 인덱스 생성 (청크별 배치 처리로 메모리 효율성 개선)
            logger.info(f"🔄 백그라운드 벡터 인덱스 생성 시작: {len(documents)}개 청크")

            # 배치 크기로 나누어 처리 (메모리 효율성)
            batch_size = 50
            total_batches = (len(documents) + batch_size - 1) // batch_size

            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                batch_num = (i // batch_size) + 1

                logger.info(f"📦 배치 {batch_num}/{total_batches} 처리 중 ({len(batch)}개 청크)")

                if i == 0:
                    # 첫 번째 배치: 새 인덱스 생성
                    success = await vector_service.create_index_from_documents(batch)
                else:
                    # 이후 배치: 기존 인덱스에 추가
                    success = await vector_service.add_documents(batch)

                if not success:
                    logger.error(f"❌ 배치 {batch_num} 처리 실패")
                    await self._update_document_status(document_id, "failed")
                    return

                # 진행 상황 로깅
                progress = (batch_num / total_batches) * 100
                logger.info(f"📊 진행률: {progress:.1f}%")

            # 성공 상태로 업데이트
            await self._update_document_status(document_id, "completed")
            logger.info(f"✅ 백그라운드 처리 완료: {document_id} ({len(documents)}개 청크)")

        except Exception as e:
            logger.error(f"❌ 백그라운드 처리 실패 ({document_id}): {e}")
            await self._update_document_status(document_id, "failed")

    async def _update_document_status(self, document_id: str, status: str):
        """문서 처리 상태 업데이트"""
        try:
            from ..config.database import AsyncSessionLocal
            from sqlalchemy import update
            from ..config.database import Document as DBDocument

            async with AsyncSessionLocal() as session:
                stmt = update(DBDocument).where(
                    DBDocument.id == document_id
                ).values(processing_status=status)
                await session.execute(stmt)
                await session.commit()

        except Exception as e:
            logger.error(f"문서 상태 업데이트 실패 ({document_id} -> {status}): {e}")


# 전역 PDF 서비스 인스턴스
_pdf_service: Optional[PDFParsingService] = None

def get_pdf_service() -> PDFParsingService:
    """PDF 서비스 싱글톤 인스턴스 반환"""
    global _pdf_service
    if _pdf_service is None:
        _pdf_service = PDFParsingService()
    return _pdf_service
