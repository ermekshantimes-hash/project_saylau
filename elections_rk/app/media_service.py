# Media Service module (Task #11)
# S3-compatible storage (MinIO) для файлов, изображений, видео

import os
import io
import hashlib
from datetime import datetime, timedelta
from typing import Optional, BinaryIO, Tuple
from minio import Minio
from minio.error import S3Error
from PIL import Image
import magic

from app.config import settings


class MediaService:
    """
    Сервис для работы с медиа-файлами через S3-compatible storage
    """
    
    def __init__(self):
        # Конфигурация MinIO/S3
        self.endpoint = os.getenv("S3_ENDPOINT", "localhost:9000")
        self.access_key = os.getenv("S3_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("S3_SECRET_KEY", "minioadmin")
        self.secure = os.getenv("S3_SECURE", "false").lower() == "true"
        
        # Инициализация клиента
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        # Bucket names
        self.buckets = {
            "protocols": "protocols",
            "photos": "observer-photos",
            "documents": "observer-documents",
            "incidents": "incident-media",
            "avatars": "user-avatars",
            "temp": "temp-uploads"
        }
        
        # Создать buckets если не существуют
        self._ensure_buckets()
        
        # MIME types
        self.allowed_image_types = [
            "image/jpeg", "image/png", "image/gif", "image/webp"
        ]
        self.allowed_document_types = [
            "application/pdf",
            "image/jpeg", "image/png",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]
        self.allowed_video_types = [
            "video/mp4", "video/mpeg", "video/quicktime", "video/x-msvideo"
        ]
    
    def _ensure_buckets(self):
        """Создать необходимые buckets"""
        for bucket_name in self.buckets.values():
            try:
                if not self.client.bucket_exists(bucket_name):
                    self.client.make_bucket(bucket_name)
                    print(f"✓ Bucket created: {bucket_name}")
            except S3Error as e:
                print(f"✗ Error creating bucket {bucket_name}: {e}")
    
    def _generate_file_hash(self, file_data: bytes) -> str:
        """Генерация SHA256 хеша файла"""
        return hashlib.sha256(file_data).hexdigest()
    
    def _detect_mime_type(self, file_data: bytes, filename: str) -> str:
        """Определение MIME типа файла"""
        try:
            mime = magic.Magic(mime=True)
            detected = mime.from_buffer(file_data)
            return detected
        except Exception:
            # Fallback по расширению
            ext = os.path.splitext(filename)[1].lower()
            mime_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".pdf": "application/pdf",
                ".mp4": "video/mp4",
                ".avi": "video/x-msvideo",
                ".mov": "video/quicktime"
            }
            return mime_map.get(ext, "application/octet-stream")
    
    def _validate_file_size(self, size: int, max_size_mb: int = 50) -> bool:
        """Проверка размера файла"""
        max_bytes = max_size_mb * 1024 * 1024
        return size <= max_bytes
    
    def _generate_object_name(self, category: str, filename: str, user_id: Optional[int] = None) -> str:
        """Генерация имени объекта в S3"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        ext = os.path.splitext(filename)[1]
        
        if user_id:
            return f"{category}/{user_id}/{timestamp}_{filename}"
        else:
            return f"{category}/{timestamp}_{filename}"
    
    # === UPLOAD METHODS ===
    
    def upload_protocol(
        self,
        file_data: BinaryIO,
        filename: str,
        precinct_id: int,
        uploader_id: int
    ) -> dict:
        """
        Загрузка протокола
        """
        # Читаем данные
        content = file_data.read()
        size = len(content)
        
        # Валидация размера (максимум 50 MB)
        if not self._validate_file_size(size, max_size_mb=50):
            raise ValueError("File size exceeds 50 MB limit")
        
        # Определяем MIME type
        mime_type = self._detect_mime_type(content, filename)
        
        # Валидация типа
        if mime_type not in self.allowed_image_types + self.allowed_document_types:
            raise ValueError(f"Invalid file type: {mime_type}")
        
        # Генерация хеша
        file_hash = self._generate_file_hash(content)
        
        # Генерация имени объекта
        object_name = f"precinct_{precinct_id}/uploader_{uploader_id}/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
        
        # Загрузка в MinIO
        try:
            self.client.put_object(
                bucket_name=self.buckets["protocols"],
                object_name=object_name,
                data=io.BytesIO(content),
                length=size,
                content_type=mime_type
            )
            
            # Генерация URL
            url = f"s3://{self.buckets['protocols']}/{object_name}"
            
            return {
                "url": url,
                "object_name": object_name,
                "bucket": self.buckets["protocols"],
                "file_hash": file_hash,
                "size": size,
                "mime_type": mime_type
            }
        except S3Error as e:
            raise Exception(f"S3 upload error: {e}")
    
    def upload_observer_photo(
        self,
        file_data: BinaryIO,
        filename: str,
        observer_id: int,
        photo_type: str = "id"  # "id", "certificate", "selfie"
    ) -> dict:
        """
        Загрузка фото наблюдателя (удостоверение, сертификат, селфи)
        """
        content = file_data.read()
        size = len(content)
        
        # Валидация размера (максимум 10 MB)
        if not self._validate_file_size(size, max_size_mb=10):
            raise ValueError("Image size exceeds 10 MB limit")
        
        # Определяем MIME type
        mime_type = self._detect_mime_type(content, filename)
        
        # Валидация что это изображение
        if mime_type not in self.allowed_image_types:
            raise ValueError(f"Invalid image type: {mime_type}")
        
        # Генерация хеша
        file_hash = self._generate_file_hash(content)
        
        # Создание thumbnail
        thumbnail_data = self._create_thumbnail(content, max_size=300)
        
        # Генерация имени объекта
        object_name = f"observer_{observer_id}/{photo_type}/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
        thumbnail_name = f"observer_{observer_id}/{photo_type}/thumb_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
        
        try:
            # Загрузка оригинала
            self.client.put_object(
                bucket_name=self.buckets["photos"],
                object_name=object_name,
                data=io.BytesIO(content),
                length=size,
                content_type=mime_type
            )
            
            # Загрузка thumbnail
            self.client.put_object(
                bucket_name=self.buckets["photos"],
                object_name=thumbnail_name,
                data=io.BytesIO(thumbnail_data),
                length=len(thumbnail_data),
                content_type=mime_type
            )
            
            url = f"s3://{self.buckets['photos']}/{object_name}"
            thumbnail_url = f"s3://{self.buckets['photos']}/{thumbnail_name}"
            
            return {
                "url": url,
                "thumbnail_url": thumbnail_url,
                "object_name": object_name,
                "bucket": self.buckets["photos"],
                "file_hash": file_hash,
                "size": size,
                "mime_type": mime_type
            }
        except S3Error as e:
            raise Exception(f"S3 upload error: {e}")
    
    def upload_incident_media(
        self,
        file_data: BinaryIO,
        filename: str,
        incident_id: int,
        reporter_id: int
    ) -> dict:
        """
        Загрузка медиа для инцидента (фото или видео)
        """
        content = file_data.read()
        size = len(content)
        
        # Валидация размера (максимум 100 MB для видео)
        if not self._validate_file_size(size, max_size_mb=100):
            raise ValueError("File size exceeds 100 MB limit")
        
        # Определяем MIME type
        mime_type = self._detect_mime_type(content, filename)
        
        # Валидация типа
        if mime_type not in self.allowed_image_types + self.allowed_video_types:
            raise ValueError(f"Invalid media type: {mime_type}")
        
        # Генерация хеша
        file_hash = self._generate_file_hash(content)
        
        # Генерация имени объекта
        object_name = f"incident_{incident_id}/reporter_{reporter_id}/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
        
        try:
            self.client.put_object(
                bucket_name=self.buckets["incidents"],
                object_name=object_name,
                data=io.BytesIO(content),
                length=size,
                content_type=mime_type
            )
            
            url = f"s3://{self.buckets['incidents']}/{object_name}"
            
            return {
                "url": url,
                "object_name": object_name,
                "bucket": self.buckets["incidents"],
                "file_hash": file_hash,
                "size": size,
                "mime_type": mime_type
            }
        except S3Error as e:
            raise Exception(f"S3 upload error: {e}")
    
    # === THUMBNAIL & IMAGE PROCESSING ===
    
    def _create_thumbnail(self, image_data: bytes, max_size: int = 300) -> bytes:
        """
        Создание thumbnail изображения
        """
        try:
            img = Image.open(io.BytesIO(image_data))
            
            # Сохранение ориентации (EXIF)
            if hasattr(img, '_getexif') and img._getexif() is not None:
                exif = dict(img._getexif().items())
                if 274 in exif:  # Orientation tag
                    if exif[274] == 3:
                        img = img.rotate(180, expand=True)
                    elif exif[274] == 6:
                        img = img.rotate(270, expand=True)
                    elif exif[274] == 8:
                        img = img.rotate(90, expand=True)
            
            # Resize с сохранением пропорций
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Конвертация в RGB если нужно
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Сохранение в bytes
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=85, optimize=True)
            return output.getvalue()
        except Exception as e:
            raise Exception(f"Thumbnail creation error: {e}")
    
    # === DOWNLOAD METHODS ===
    
    def get_file(self, bucket: str, object_name: str) -> Tuple[bytes, str]:
        """
        Скачать файл из S3
        Возвращает (file_data, mime_type)
        """
        try:
            response = self.client.get_object(bucket, object_name)
            data = response.read()
            mime_type = response.headers.get('Content-Type', 'application/octet-stream')
            return data, mime_type
        except S3Error as e:
            raise Exception(f"S3 download error: {e}")
        finally:
            if response:
                response.close()
                response.release_conn()
    
    def get_presigned_url(
        self,
        bucket: str,
        object_name: str,
        expires: int = 3600
    ) -> str:
        """
        Генерация presigned URL для временного доступа
        expires в секундах (по умолчанию 1 час)
        """
        try:
            url = self.client.presigned_get_object(
                bucket_name=bucket,
                object_name=object_name,
                expires=timedelta(seconds=expires)
            )
            return url
        except S3Error as e:
            raise Exception(f"Presigned URL error: {e}")
    
    # === DELETE METHODS ===
    
    def delete_file(self, bucket: str, object_name: str) -> bool:
        """
        Удалить файл из S3
        """
        try:
            self.client.remove_object(bucket, object_name)
            return True
        except S3Error as e:
            print(f"Delete error: {e}")
            return False
    
    # === UTILITY METHODS ===
    
    def list_files(self, bucket: str, prefix: str = "") -> list:
        """
        Список файлов в bucket
        """
        try:
            objects = self.client.list_objects(bucket, prefix=prefix, recursive=True)
            return [
                {
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None
                }
                for obj in objects
            ]
        except S3Error as e:
            raise Exception(f"List files error: {e}")
    
    def get_file_info(self, bucket: str, object_name: str) -> dict:
        """
        Получить метаданные файла
        """
        try:
            stat = self.client.stat_object(bucket, object_name)
            return {
                "object_name": stat.object_name,
                "size": stat.size,
                "etag": stat.etag,
                "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
                "content_type": stat.content_type,
                "metadata": stat.metadata
            }
        except S3Error as e:
            raise Exception(f"File info error: {e}")
    
    def calculate_storage_usage(self) -> dict:
        """
        Подсчёт использования хранилища по buckets
        """
        usage = {}
        
        for name, bucket in self.buckets.items():
            try:
                objects = self.client.list_objects(bucket, recursive=True)
                total_size = sum(obj.size for obj in objects)
                file_count = sum(1 for _ in self.client.list_objects(bucket, recursive=True))
                
                usage[name] = {
                    "bucket": bucket,
                    "file_count": file_count,
                    "total_size_bytes": total_size,
                    "total_size_mb": round(total_size / (1024 * 1024), 2)
                }
            except S3Error:
                usage[name] = {
                    "bucket": bucket,
                    "file_count": 0,
                    "total_size_bytes": 0,
                    "total_size_mb": 0
                }
        
        return usage


# Singleton instance
_media_service = None

def get_media_service() -> MediaService:
    """Получить глобальный экземпляр MediaService"""
    global _media_service
    if _media_service is None:
        _media_service = MediaService()
    return _media_service
