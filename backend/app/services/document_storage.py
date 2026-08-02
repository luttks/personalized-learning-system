import hashlib
import os
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile


class DocumentStorageError(Exception):
    """Base error for upload validation and local storage failures."""


class EmptyDocumentError(DocumentStorageError):
    pass


class DocumentTooLargeError(DocumentStorageError):
    pass


class UnsupportedDocumentTypeError(DocumentStorageError):
    pass


class InvalidDocumentSignatureError(DocumentStorageError):
    pass


@dataclass(frozen=True)
class StoredDocument:
    storage_key: str
    original_name: str
    content_type: str
    size_bytes: int
    checksum_sha256: str


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
}

CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


class LocalDocumentStorage:
    def __init__(
        self,
        root: str | Path,
        max_upload_bytes: int,
        chunk_bytes: int = 1024 * 1024,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.max_upload_bytes = max_upload_bytes
        self.chunk_bytes = chunk_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, upload: UploadFile) -> StoredDocument:
        original_name = Path(upload.filename or "").name
        extension = Path(original_name).suffix.lower()
        if not original_name or extension not in SUPPORTED_EXTENSIONS:
            raise UnsupportedDocumentTypeError(
                "Định dạng hỗ trợ: PDF, DOCX, PPTX, TXT, PNG và JPEG."
            )

        storage_key = self._new_storage_key(extension)
        destination = self._resolve_key(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.part")
        digest = hashlib.sha256()
        size = 0

        try:
            with temporary.open("wb") as output:
                while True:
                    chunk = await upload.read(self.chunk_bytes)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.max_upload_bytes:
                        raise DocumentTooLargeError(
                            f"Tài liệu vượt giới hạn {self.max_upload_bytes} bytes."
                        )
                    digest.update(chunk)
                    output.write(chunk)

            if size == 0:
                raise EmptyDocumentError("Tài liệu không được rỗng.")
            content_type = self._detect_content_type(temporary, extension)
            os.replace(temporary, destination)
            return StoredDocument(
                storage_key=storage_key,
                original_name=original_name[:255],
                content_type=content_type,
                size_bytes=size,
                checksum_sha256=digest.hexdigest(),
            )
        except DocumentStorageError:
            temporary.unlink(missing_ok=True)
            raise
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise DocumentStorageError("Không thể lưu tài liệu.") from error
        finally:
            await upload.close()

    def delete(self, storage_key: str) -> None:
        self._resolve_key(storage_key).unlink(missing_ok=True)

    def path_for(self, storage_key: str) -> Path:
        return self._resolve_key(storage_key)

    def verify(
        self,
        storage_key: str,
        *,
        expected_size: int,
        expected_checksum: str,
    ) -> None:
        path = self._resolve_key(storage_key)
        if not path.is_file():
            raise DocumentStorageError("Không tìm thấy file gốc trong storage.")

        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as source:
            while chunk := source.read(self.chunk_bytes):
                size += len(chunk)
                digest.update(chunk)
        if size != expected_size or digest.hexdigest() != expected_checksum:
            raise InvalidDocumentSignatureError(
                "Checksum hoặc kích thước file không khớp metadata."
            )

    def _new_storage_key(self, extension: str) -> str:
        token = uuid.uuid4().hex
        return f"documents/{token[:2]}/{token}{extension}"

    def _resolve_key(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise DocumentStorageError("Storage key không hợp lệ.")
        return candidate

    @staticmethod
    def _detect_content_type(path: Path, extension: str) -> str:
        with path.open("rb") as source:
            header = source.read(16)

        if extension == ".pdf" and header.startswith(b"%PDF-"):
            return CONTENT_TYPES[extension]
        if extension == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
            return CONTENT_TYPES[extension]
        if extension in {".jpg", ".jpeg"} and header.startswith(b"\xff\xd8\xff"):
            return CONTENT_TYPES[extension]
        if extension == ".txt":
            try:
                path.read_bytes().decode("utf-8-sig")
            except UnicodeDecodeError as error:
                raise InvalidDocumentSignatureError(
                    "TXT phải sử dụng encoding UTF-8."
                ) from error
            if b"\x00" in header:
                raise InvalidDocumentSignatureError("TXT chứa byte nhị phân.")
            return CONTENT_TYPES[extension]
        if extension in {".docx", ".pptx"} and LocalDocumentStorage._is_open_xml(
            path, extension
        ):
            return CONTENT_TYPES[extension]
        raise InvalidDocumentSignatureError(
            "Nội dung file không khớp với phần mở rộng đã chọn."
        )

    @staticmethod
    def _is_open_xml(path: Path, extension: str) -> bool:
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" not in names or len(names) > 10_000:
                    return False
                marker = "word/document.xml" if extension == ".docx" else "ppt/presentation.xml"
                return marker in names
        except (OSError, zipfile.BadZipFile):
            return False
