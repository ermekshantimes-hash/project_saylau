# API endpoints для Media Service (Task #11)

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import io

from app.database import get_db
from app.models_extended import User
from app.routes_auth import get_current_user, require_role
from app.media_service import get_media_service

router = APIRouter(prefix="/api/media", tags=["Media Service"])


# Schemas
class UploadResponse(BaseModel):
    url: str
    thumbnail_url: Optional[str] = None
    file_hash: str
    size: int
    mime_type: str


class FileInfoResponse(BaseModel):
    object_name: str
    size: int
    content_type: str
    last_modified: Optional[str]


class StorageUsageResponse(BaseModel):
    bucket: str
    file_count: int
    total_size_mb: float


# Endpoints

@router.post("/upload/protocol", response_model=UploadResponse)
async def upload_protocol_file(
    precinct_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Загрузить файл протокола
    
    Поддерживаемые форматы: JPEG, PNG, PDF
    Максимальный размер: 50 MB
    """
    media_service = get_media_service()
    
    try:
        result = media_service.upload_protocol(
            file_data=file.file,
            filename=file.filename,
            precinct_id=precinct_id,
            uploader_id=current_user.id
        )
        
        return UploadResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")


@router.post("/upload/observer-photo", response_model=UploadResponse)
async def upload_observer_photo(
    observer_id: int = Form(...),
    photo_type: str = Form(..., description="id, certificate, or selfie"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Загрузить фото наблюдателя
    
    Типы фото:
    - id: удостоверение личности
    - certificate: сертификат обучения
    - selfie: селфи для check-in
    
    Поддерживаемые форматы: JPEG, PNG
    Максимальный размер: 10 MB
    """
    if photo_type not in ["id", "certificate", "selfie"]:
        raise HTTPException(status_code=400, detail="Invalid photo_type")
    
    media_service = get_media_service()
    
    try:
        result = media_service.upload_observer_photo(
            file_data=file.file,
            filename=file.filename,
            observer_id=observer_id,
            photo_type=photo_type
        )
        
        return UploadResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")


@router.post("/upload/incident-media", response_model=UploadResponse)
async def upload_incident_media(
    incident_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Загрузить медиа для инцидента (фото или видео)
    
    Поддерживаемые форматы: JPEG, PNG, MP4, MOV, AVI
    Максимальный размер: 100 MB
    """
    media_service = get_media_service()
    
    try:
        result = media_service.upload_incident_media(
            file_data=file.file,
            filename=file.filename,
            incident_id=incident_id,
            reporter_id=current_user.id
        )
        
        return UploadResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")


@router.get("/download/{bucket}/{object_name:path}")
async def download_file(
    bucket: str,
    object_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    Скачать файл из S3
    
    Buckets:
    - protocols
    - observer-photos
    - observer-documents
    - incident-media
    - user-avatars
    """
    media_service = get_media_service()
    
    try:
        file_data, mime_type = media_service.get_file(bucket, object_name)
        
        # Определяем имя файла
        filename = object_name.split('/')[-1]
        
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")


@router.get("/presigned-url/{bucket}/{object_name:path}")
async def get_presigned_url(
    bucket: str,
    object_name: str,
    expires: int = Query(3600, description="URL expiration in seconds"),
    current_user: User = Depends(get_current_user)
):
    """
    Получить presigned URL для временного доступа
    
    По умолчанию URL действителен 1 час (3600 секунд)
    """
    media_service = get_media_service()
    
    try:
        url = media_service.get_presigned_url(bucket, object_name, expires)
        return {
            "url": url,
            "expires_in": expires
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.delete("/delete/{bucket}/{object_name:path}")
async def delete_file(
    bucket: str,
    object_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Удалить файл из S3
    Только ADMIN и COORD
    """
    media_service = get_media_service()
    
    try:
        success = media_service.delete_file(bucket, object_name)
        if success:
            return {"message": "File deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Delete failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/list/{bucket}")
async def list_files(
    bucket: str,
    prefix: str = Query("", description="Filter by prefix"),
    current_user: User = Depends(require_role(["ADMIN", "COORD"]))
):
    """
    Список файлов в bucket
    Только ADMIN и COORD
    """
    media_service = get_media_service()
    
    try:
        files = media_service.list_files(bucket, prefix)
        return {
            "bucket": bucket,
            "prefix": prefix,
            "files": files,
            "count": len(files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/info/{bucket}/{object_name:path}", response_model=FileInfoResponse)
async def get_file_info(
    bucket: str,
    object_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    Получить метаданные файла
    """
    media_service = get_media_service()
    
    try:
        info = media_service.get_file_info(bucket, object_name)
        return FileInfoResponse(**info)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")


@router.get("/storage/usage")
async def get_storage_usage(
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """
    Получить статистику использования хранилища
    Только ADMIN
    """
    media_service = get_media_service()
    
    try:
        usage = media_service.calculate_storage_usage()
        
        # Подсчитать общее использование
        total_files = sum(bucket['file_count'] for bucket in usage.values())
        total_size_mb = sum(bucket['total_size_mb'] for bucket in usage.values())
        
        return {
            "by_bucket": usage,
            "total": {
                "file_count": total_files,
                "total_size_mb": round(total_size_mb, 2),
                "total_size_gb": round(total_size_mb / 1024, 2)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/health")
async def media_service_health() -> dict:
    """
    Проверка работоспособности media service
    Публичный endpoint
    """
    media_service = get_media_service()
    
    try:
        # Попытка листинга buckets для проверки подключения
        buckets_status = {}
        
        for name, bucket in media_service.buckets.items():
            try:
                exists = media_service.client.bucket_exists(bucket)
                buckets_status[name] = "OK" if exists else "NOT_FOUND"
            except Exception:
                buckets_status[name] = "ERROR"
        
        all_ok = all(status == "OK" for status in buckets_status.values())
        
        return {
            "status": "healthy" if all_ok else "degraded",
            "endpoint": media_service.endpoint,
            "buckets": buckets_status
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
