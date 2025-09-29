import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from ..config.database import get_db, Document
from ..config.settings import settings
from ..models.request_models import DocumentType
from ..models.response_models import UploadResponse
from ..services.pdf_service import get_pdf_service
from ..services.vector_service import get_vector_service

router = APIRouter(prefix="/api/upload", tags=["파일 업로드"])


@router.post("", response_model=UploadResponse, summary="PDF 파일 업로드 및 처리")
async def upload_document(
    file: UploadFile = File(..., description="업로드할 PDF 파일"),
    document_type: DocumentType = Form(DocumentType.DATASHEET, description="문서 타입"),
    product_family: Optional[str] = Form(None, description="제품군"),
    product_model: Optional[str] = Form(None, description="제품 모델"),
    version: Optional[str] = Form(None, description="버전"),
    language: str = Form("ko", description="언어"),
    db: AsyncSession = Depends(get_db)
):
    """
    PDF 파일을 업로드하고 벡터 데이터베이스에 저장합니다.

    처리 과정:
    1. 파일 검증 및 저장
    2. PDF 텍스트 추출
    3. 텍스트 청킹
    4. 벡터 임베딩 생성
    5. 데이터베이스 메타데이터 저장
    """
    try:
        # 1. 파일 검증
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="PDF 파일만 업로드 가능합니다."
            )

        # 파일 크기 검증
        file_content = await file.read()
        if len(file_content) > settings.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"파일 크기가 너무 큽니다. 최대 {settings.max_file_size // (1024*1024)}MB까지 허용됩니다."
            )

        # 2. 문서 ID 생성 및 데이터베이스 저장
        document_id = str(uuid.uuid4())

        # PDF 서비스로 파일 저장
        pdf_service = get_pdf_service()
        file_path = await pdf_service.save_uploaded_file(file_content, file.filename)

        # 폼 데이터 검증 및 정제 (frontend에서 'string' 리터럴 값 보내는 경우 처리)
        def clean_form_value(value: Optional[str]) -> Optional[str]:
            """폼에서 받은 값을 정제하여 None 또는 유효한 문자열 반환"""
            if value is None or value.lower() in ['', 'none', 'null', 'string']:
                return None
            return value.strip() if value.strip() else None

        # 데이터베이스에 문서 정보 저장
        document = Document(
            id=document_id,
            filename=Path(file_path).name,
            original_name=file.filename,
            file_path=file_path,
            file_size=len(file_content),
            document_type=document_type.value,
            product_family=clean_form_value(product_family),
            product_model=clean_form_value(product_model),
            version=clean_form_value(version),
            language=language,
            processing_status="processing"
        )

        db.add(document)
        await db.commit()

        logger.info(f"문서 업로드 시작: {document_id}")

        # 3. 개선된 비동기 처리 시작 (백그라운드에서 실행)
        import asyncio
        vector_service = await get_vector_service()
        asyncio.create_task(
            pdf_service.process_pdf_background(file_path, document_id, vector_service)
        )

        return UploadResponse(
            document_id=document_id,
            status="processing",
            message="파일이 성공적으로 업로드되었습니다. 처리가 진행 중입니다.",
            file_info={
                "filename": file.filename,
                "size_mb": round(len(file_content) / (1024*1024), 2),
                "type": document_type.value
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파일 업로드 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"파일 업로드 중 오류가 발생했습니다: {str(e)}"
        )


async def process_document_background(document_id: str, file_path: str):
    """백그라운드에서 문서 처리"""
    try:
        logger.info(f"백그라운드 문서 처리 시작: {document_id}")

        # PDF 서비스로 텍스트 추출 및 청킹
        pdf_service = get_pdf_service()
        chunks, metadata = await pdf_service.process_pdf_file(file_path, document_id)

        logger.info(f"PDF 처리 완료: {len(chunks)}개 청크 생성")

        # 벡터 서비스로 임베딩 생성 및 저장
        vector_service = await get_vector_service()
        success = await vector_service.add_documents(chunks, "default")

        # 데이터베이스 상태 업데이트
        async with get_db().__anext__() as db:
            from sqlalchemy import select, update

            # 문서 상태 업데이트
            await db.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(
                    processing_status="completed" if success else "failed",
                    page_count=metadata.get("page_count", 0)
                )
            )
            await db.commit()

        if success:
            logger.info(f"문서 처리 완료: {document_id}")
        else:
            logger.error(f"문서 처리 실패: {document_id}")

    except Exception as e:
        logger.error(f"백그라운드 문서 처리 실패 ({document_id}): {e}")

        # 오류 상태로 업데이트
        try:
            async with get_db().__anext__() as db:
                from sqlalchemy import update
                await db.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(processing_status="failed")
                )
                await db.commit()
        except Exception as update_error:
            logger.error(f"상태 업데이트 실패: {update_error}")


@router.get("/status/{document_id}", summary="문서 처리 상태 확인")
async def get_document_status(
    document_id: str,
    db: AsyncSession = Depends(get_db)
):
    """업로드된 문서의 처리 상태를 확인합니다."""
    try:
        from sqlalchemy import select

        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=404,
                detail="문서를 찾을 수 없습니다."
            )

        return {
            "document_id": document.id,
            "filename": document.original_name,
            "status": document.processing_status,
            "upload_date": document.upload_date,
            "page_count": document.page_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 상태 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail="문서 상태를 조회하는 중 오류가 발생했습니다."
        )


@router.delete("/{document_id}", summary="업로드된 문서 삭제")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db)
):
    """업로드된 문서와 관련 데이터를 삭제합니다."""
    try:
        from sqlalchemy import select, delete

        # 문서 존재 여부 확인
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=404,
                detail="문서를 찾을 수 없습니다."
            )

        # 파일 시스템에서 파일 삭제
        try:
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
                logger.info(f"파일 삭제: {document.file_path}")
        except Exception as e:
            logger.warning(f"파일 삭제 실패: {e}")

        # 벡터 청크 삭제
        from ..config.database import VectorChunk
        await db.execute(
            delete(VectorChunk).where(VectorChunk.document_id == document_id)
        )

        # 문서 삭제
        await db.execute(
            delete(Document).where(Document.id == document_id)
        )

        await db.commit()

        logger.info(f"문서 삭제 완료: {document_id}")

        return JSONResponse(
            content={
                "message": "문서가 성공적으로 삭제되었습니다.",
                "document_id": document_id
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 삭제 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail="문서 삭제 중 오류가 발생했습니다."
        )