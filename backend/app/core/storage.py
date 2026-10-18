import asyncio
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

# Optional imports for S3/MinIO backends
try:
    import boto3
    from botocore.client import BaseClient
    from botocore.exceptions import BotoCoreError, ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    BaseClient = None  # type: ignore
    BotoCoreError = Exception  # type: ignore
    ClientError = Exception  # type: ignore

try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    S3Error = Exception  # type: ignore

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Base exception for storage-related errors."""


class StorageConfigurationError(StorageError):
    """Raised when storage is misconfigured."""


class StorageBackend(ABC):
    """
    Abstract base class for storage backends.

    Implementations must be fully async-compatible; blocking libraries should be
    wrapped via asyncio.to_thread.
    """

    @abstractmethod
    async def upload(self, path: str, file: bytes) -> str:
        """
        Upload a file to the storage backend.

        Args:
            path: Destination path (key) within the storage backend.
            file: Raw bytes to be uploaded.

        Returns:
            The canonical storage path/key of the uploaded file.
        """
        raise NotImplementedError

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """
        Download a file from the storage backend.

        Args:
            path: Path/key of the file to download.

        Returns:
            File content as bytes.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """
        Delete a file from the storage backend.

        Args:
            path: Path/key of the file to delete.

        Returns:
            True if the file was deleted or did not exist, False otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    async def list(self, prefix: str) -> List[str]:
        """
        List file paths/keys under a given prefix.

        Args:
            prefix: Path/prefix to list from.

        Returns:
            List of file paths/keys.
        """
        raise NotImplementedError

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """
        Check if a file exists in the storage backend.

        Args:
            path: Path/key to check.

        Returns:
            True if the file exists, False otherwise.
        """
        raise NotImplementedError


class LocalStorage(StorageBackend):
    """
    Local filesystem storage implementation.

    Files are stored under a configured root directory. Paths are treated as
    relative to this root and normalized to prevent directory traversal.
    """

    def __init__(self, base_path: Optional[str] = None) -> None:
        root = base_path or os.getenv("STORAGE_PATH", "/data/storage")
        self.base_path = Path(root).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info("Initialized LocalStorage at %s", self.base_path)

    def _full_path(self, path: str) -> Path:
        """
        Resolve a user-provided path/key to an absolute path under the storage root.

        Raises:
            StorageError: If path escapes the storage root (directory traversal).
        """
        # Normalize and avoid absolute paths
        safe_path = Path(path.lstrip("/"))
        full_path = (self.base_path / safe_path).resolve()

        if not str(full_path).startswith(str(self.base_path)):
            logger.error(
                "Attempted directory traversal outside storage root: %s -> %s",
                path,
                full_path,
            )
            raise StorageError("Invalid storage path")

        return full_path

    async def upload(self, path: str, file: bytes) -> str:
        full_path = self._full_path(path)

        def _write() -> None:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, "wb") as f:
                f.write(file)

        try:
            await asyncio.to_thread(_write)
            logger.debug(f"Uploaded file to local storage: {full_path}")
            # Return normalized relative path
            rel_path = full_path.relative_to(self.base_path)
            return str(rel_path).replace("\\", "/")
        except OSError as exc:
            logger.exception("Failed to upload file to local storage: %s", exc)
            raise StorageError("Failed to upload file to local storage") from exc

    async def download(self, path: str) -> bytes:
        full_path = self._full_path(path)

        def _read() -> bytes:
            with open(full_path, "rb") as f:
                return f.read()

        try:
            data = await asyncio.to_thread(_read)
            logger.debug(f"Downloaded file from local storage: {full_path}")
            return data
        except FileNotFoundError as exc:
            logger.warning("File not found in local storage: %s", full_path)
            raise StorageError("File not found") from exc
        except OSError as exc:
            logger.exception("Failed to download file from local storage: %s", exc)
            raise StorageError("Failed to download file from local storage") from exc

    async def delete(self, path: str) -> bool:
        full_path = self._full_path(path)

        def _delete() -> bool:
            if not full_path.exists():
                return True
            try:
                full_path.unlink()
                return True
            except OSError:
                return False

        try:
            deleted = await asyncio.to_thread(_delete)
            if deleted:
                logger.debug(f"Deleted file from local storage: {full_path}")
            else:
                logger.error("Failed to delete file from local storage: %s", full_path)
            return deleted
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error deleting file from local storage: %s", exc)
            raise StorageError("Failed to delete file from local storage") from exc

    async def list(self, prefix: str) -> List[str]:
        prefix_path = self._full_path(prefix)

        def _list() -> List[str]:
            if not prefix_path.exists():
                return []
            if prefix_path.is_file():
                rel = prefix_path.relative_to(self.base_path)
                return [str(rel).replace("\\", "/")]
            results: List[str] = []
            for p in prefix_path.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(self.base_path)
                    results.append(str(rel).replace("\\", "/"))
            return results

        try:
            files = await asyncio.to_thread(_list)
            logger.debug(
                f"Listed {len(files)} files from local storage with prefix {prefix or ''}"
            )
            return files
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to list files from local storage: %s", exc)
            raise StorageError("Failed to list files from local storage") from exc

    async def exists(self, path: str) -> bool:
        full_path = self._full_path(path)

        def _exists() -> bool:
            return full_path.exists()

        try:
            return await asyncio.to_thread(_exists)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error checking existence in local storage: %s", exc)
            raise StorageError("Failed to check file existence") from exc


class S3Storage(StorageBackend):
    """
    Amazon S3-compatible storage using boto3.

    Configuration via environment variables:
      - STORAGE_ENDPOINT (optional; omit or empty for AWS S3)
      - STORAGE_ACCESS_KEY
      - STORAGE_SECRET_KEY
      - STORAGE_BUCKET
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> None:
        if not BOTO3_AVAILABLE:
            raise StorageConfigurationError(
                "boto3 is required for S3Storage. Install it with: pip install boto3"
            )
        
        self.endpoint = endpoint or os.getenv("STORAGE_ENDPOINT") or None
        self.access_key = access_key or os.getenv("STORAGE_ACCESS_KEY")
        self.secret_key = secret_key or os.getenv("STORAGE_SECRET_KEY")
        self.bucket = bucket or os.getenv("STORAGE_BUCKET")

        if not self.bucket:
            raise StorageConfigurationError("STORAGE_BUCKET is not configured")
        if not self.access_key or not self.secret_key:
            raise StorageConfigurationError("STORAGE_ACCESS_KEY/SECRET_KEY not configured")

        import boto3  # Import here to ensure it's available
        session = boto3.session.Session()
        client_params = {
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
        }
        if self.endpoint:
            client_params["endpoint_url"] = self.endpoint

        self.client: BaseClient = session.client("s3", **client_params)
        logger.info(
            "Initialized S3Storage for bucket %s at endpoint %s",
            self.bucket,
            self.endpoint or "aws",
        )

    def _normalize_key(self, path: str) -> str:
        return path.lstrip("/")

    async def upload(self, path: str, file: bytes) -> str:
        key = self._normalize_key(path)

        def _upload() -> None:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=file)

        try:
            await asyncio.to_thread(_upload)
            logger.debug(f"Uploaded file to S3: bucket={self.bucket} key={key}")
            return key
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Failed to upload file to S3: %s", exc)
            raise StorageError("Failed to upload file to S3") from exc

    async def download(self, path: str) -> bytes:
        key = self._normalize_key(path)

        def _download() -> bytes:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()

        try:
            data = await asyncio.to_thread(_download)
            logger.debug(f"Downloaded file from S3: bucket={self.bucket} key={key}")
            return data
        except self.client.exceptions.NoSuchKey as exc:
            logger.warning("File not found in S3: bucket=%s key=%s", self.bucket, key)
            raise StorageError("File not found") from exc
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Failed to download file from S3: %s", exc)
            raise StorageError("Failed to download file from S3") from exc

    async def delete(self, path: str) -> bool:
        key = self._normalize_key(path)

        def _delete() -> bool:
            try:
                self.client.delete_object(Bucket=self.bucket, Key=key)
                return True
            except self.client.exceptions.NoSuchKey:
                return True
            except (BotoCoreError, ClientError):
                return False

        try:
            deleted = await asyncio.to_thread(_delete)
            if deleted:
                logger.debug(f"Deleted file from S3: bucket={self.bucket} key={key}")
            else:
                logger.error("Failed to delete file from S3: bucket=%s key=%s", self.bucket, key)
            return deleted
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error deleting file from S3: %s", exc)
            raise StorageError("Failed to delete file from S3") from exc

    async def list(self, prefix: str) -> List[str]:
        prefix_key = self._normalize_key(prefix)

        def _list() -> List[str]:
            paginator = self.client.get_paginator("list_objects_v2")
            keys: List[str] = []
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix_key):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return keys

        try:
            keys = await asyncio.to_thread(_list)
            logger.debug(
                f"Listed {len(keys)} objects from S3 with prefix {prefix_key} (bucket={self.bucket})"
            )
            return keys
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Failed to list objects from S3: %s", exc)
            raise StorageError("Failed to list files from S3") from exc

    async def exists(self, path: str) -> bool:
        key = self._normalize_key(path)

        def _exists() -> bool:
            try:
                self.client.head_object(Bucket=self.bucket, Key=key)
                return True
            except self.client.exceptions.NoSuchKey:
                return False
            except (BotoCoreError, ClientError):
                return False

        try:
            return await asyncio.to_thread(_exists)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error checking S3 object existence: %s", exc)
            raise StorageError("Failed to check file existence in S3") from exc


class MinIOStorage(StorageBackend):
    """
    MinIO-based S3-compatible storage.

    Uses the same environment variables as S3Storage:
      - STORAGE_ENDPOINT (required, e.g., 'http://minio:9000')
      - STORAGE_ACCESS_KEY
      - STORAGE_SECRET_KEY
      - STORAGE_BUCKET
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        secure: Optional[bool] = None,
    ) -> None:
        if not MINIO_AVAILABLE:
            raise StorageConfigurationError(
                "minio is required for MinIOStorage. Install it with: pip install minio"
            )
        
        self.endpoint = endpoint or os.getenv("STORAGE_ENDPOINT")
        self.access_key = access_key or os.getenv("STORAGE_ACCESS_KEY")
        self.secret_key = secret_key or os.getenv("STORAGE_SECRET_KEY")
        self.bucket = bucket or os.getenv("STORAGE_BUCKET")

        if not self.endpoint:
            raise StorageConfigurationError("STORAGE_ENDPOINT is required for MinIO")
        if not self.bucket:
            raise StorageConfigurationError("STORAGE_BUCKET is not configured")
        if not self.access_key or not self.secret_key:
            raise StorageConfigurationError("STORAGE_ACCESS_KEY/SECRET_KEY not configured")

        # Determine secure flag from endpoint scheme if not provided
        if secure is None:
            secure = self.endpoint.startswith("https://")
        endpoint_clean = self.endpoint.replace("https://", "").replace("http://", "")

        from minio import Minio  # Import here to ensure it's available
        self.client = Minio(
            endpoint_clean,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=secure,
        )

        # Ensure bucket exists (idempotent)
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as exc:
            logger.exception("Failed to ensure MinIO bucket exists: %s", exc)
            raise StorageConfigurationError("Failed to ensure MinIO bucket") from exc

        logger.info("Initialized MinIOStorage for bucket %s at %s", self.bucket, self.endpoint)

    def _normalize_key(self, path: str) -> str:
        return path.lstrip("/")

    async def upload(self, path: str, file: bytes) -> str:
        key = self._normalize_key(path)

        def _upload() -> None:
            from io import BytesIO

            data_stream = BytesIO(file)
            size = len(file)
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=key,
                data=data_stream,
                length=size,
            )

        try:
            await asyncio.to_thread(_upload)
            logger.debug(f"Uploaded file to MinIO: bucket={self.bucket} key={key}")
            return key
        except S3Error as exc:
            logger.exception("Failed to upload file to MinIO: %s", exc)
            raise StorageError("Failed to upload file to MinIO") from exc

    async def download(self, path: str) -> bytes:
        key = self._normalize_key(path)

        def _download() -> bytes:
            response = self.client.get_object(bucket_name=self.bucket, object_name=key)
            try:
                data = response.read()
            finally:
                response.close()
                response.release_conn()
            return data

        try:
            data = await asyncio.to_thread(_download)
            logger.debug(f"Downloaded file from MinIO: bucket={self.bucket} key={key}")
            return data
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                logger.warning("File not found in MinIO: bucket=%s key=%s", self.bucket, key)
                raise StorageError("File not found") from exc
            logger.exception("Failed to download file from MinIO: %s", exc)
            raise StorageError("Failed to download file from MinIO") from exc

    async def delete(self, path: str) -> bool:
        key = self._normalize_key(path)

        def _delete() -> bool:
            try:
                self.client.remove_object(bucket_name=self.bucket, object_name=key)
                return True
            except S3Error as exc:
                if exc.code == "NoSuchKey":
                    return True
                return False

        try:
            deleted = await asyncio.to_thread(_delete)
            if deleted:
                logger.debug(f"Deleted file from MinIO: bucket={self.bucket} key={key}")
            else:
                logger.error("Failed to delete file from MinIO: bucket=%s key=%s", self.bucket, key)
            return deleted
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error deleting file from MinIO: %s", exc)
            raise StorageError("Failed to delete file from MinIO") from exc

    async def list(self, prefix: str) -> List[str]:
        prefix_key = self._normalize_key(prefix)

        def _list() -> List[str]:
            objects = self.client.list_objects(
                bucket_name=self.bucket,
                prefix=prefix_key,
                recursive=True,
            )
            return [obj.object_name for obj in objects]

        try:
            keys = await asyncio.to_thread(_list)
            logger.debug(
                f"Listed {len(keys)} objects from MinIO with prefix {prefix_key} (bucket={self.bucket})"
            )
            return keys
        except S3Error as exc:
            logger.exception("Failed to list objects from MinIO: %s", exc)
            raise StorageError("Failed to list files from MinIO") from exc

    async def exists(self, path: str) -> bool:
        key = self._normalize_key(path)

        def _exists() -> bool:
            try:
                self.client.stat_object(bucket_name=self.bucket, object_name=key)
                return True
            except S3Error as exc:
                if exc.code == "NoSuchKey":
                    return False
                return False

        try:
            return await asyncio.to_thread(_exists)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error checking MinIO object existence: %s", exc)
            raise StorageError("Failed to check file existence in MinIO") from exc


_storage_backend_instance: Optional[StorageBackend] = None


def get_storage_backend() -> StorageBackend:
    """
    Factory function returning a singleton instance of the configured storage backend.

    Reads STORAGE_BACKEND env var:
      - 'local' (default)
      - 's3'
      - 'minio'
    """
    global _storage_backend_instance
    if _storage_backend_instance is not None:
        return _storage_backend_instance

    backend_type = os.getenv("STORAGE_BACKEND", "local").lower().strip()

    try:
        if backend_type == "local":
            _storage_backend_instance = LocalStorage()
        elif backend_type == "s3":
            _storage_backend_instance = S3Storage()
        elif backend_type == "minio":
            _storage_backend_instance = MinIOStorage()
        else:
            raise StorageConfigurationError(f"Unknown STORAGE_BACKEND: {backend_type}")
    except StorageConfigurationError:
        # Re-raise configuration errors directly
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to initialize storage backend '%s': %s", backend_type, exc)
        raise StorageConfigurationError("Failed to initialize storage backend") from exc

    logger.info("Using storage backend: %s", backend_type)
    return _storage_backend_instance


class StorageService:
    """
    High-level storage service wrapper that provides convenience methods
    for file operations, including path resolution for local storage.
    """

    def __init__(self, base_path: Optional[str] = None):
        """Initialize storage service.

        Args:
            base_path: Base path for local storage (used for resolve_path)
        """
        self.backend = get_storage_backend()
        self.base_path = Path(base_path).resolve() if base_path else None

    def resolve_path(self, storage_path: str) -> str:
        """
        Resolve a storage path to a full filesystem path.

        For local storage, this returns the absolute path.
        For remote storage (S3/MinIO), this returns the path as-is.

        Args:
            storage_path: Storage path/key

        Returns:
            Full filesystem path (for local) or storage key (for remote)
        """
        if isinstance(self.backend, LocalStorage) and self.base_path:
            # For local storage, resolve to full path
            safe_path = Path(storage_path.lstrip("/"))
            full_path = (self.base_path / safe_path).resolve()
            if not str(full_path).startswith(str(self.base_path)):
                raise StorageError("Invalid storage path")
            return str(full_path)
        else:
            # For remote storage, return as-is
            return storage_path

    async def upload(self, path: str, file: bytes) -> str:
        """Upload a file to storage."""
        return await self.backend.upload(path, file)

    async def download(self, path: str) -> bytes:
        """Download a file from storage."""
        return await self.backend.download(path)

    async def delete(self, path: str) -> bool:
        """Delete a file from storage."""
        return await self.backend.delete(path)

    async def list(self, prefix: str) -> List[str]:
        """List files with prefix."""
        return await self.backend.list(prefix)

    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        return await self.backend.exists(path)