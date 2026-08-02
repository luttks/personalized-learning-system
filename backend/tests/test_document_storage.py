import asyncio
from io import BytesIO

import pytest
from app.services.document_storage import (
    DocumentTooLargeError,
    InvalidDocumentSignatureError,
    LocalDocumentStorage,
    UnsupportedDocumentTypeError,
)
from fastapi import UploadFile


def upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=name)


def test_storage_accepts_pdf_and_verifies_checksum(tmp_path) -> None:
    storage = LocalDocumentStorage(tmp_path, max_upload_bytes=1024)
    result = asyncio.run(storage.save_upload(upload("lesson.pdf", b"%PDF-1.7\nbody")))

    assert result.content_type == "application/pdf"
    assert result.size_bytes == 13
    storage.verify(
        result.storage_key,
        expected_size=result.size_bytes,
        expected_checksum=result.checksum_sha256,
    )


def test_storage_rejects_wrong_signature(tmp_path) -> None:
    storage = LocalDocumentStorage(tmp_path, max_upload_bytes=1024)

    with pytest.raises(InvalidDocumentSignatureError):
        asyncio.run(storage.save_upload(upload("lesson.pdf", b"not a pdf")))


def test_storage_rejects_unsupported_extension(tmp_path) -> None:
    storage = LocalDocumentStorage(tmp_path, max_upload_bytes=1024)

    with pytest.raises(UnsupportedDocumentTypeError):
        asyncio.run(storage.save_upload(upload("lesson.exe", b"MZ")))


def test_storage_rejects_oversized_upload(tmp_path) -> None:
    storage = LocalDocumentStorage(tmp_path, max_upload_bytes=4)

    with pytest.raises(DocumentTooLargeError):
        asyncio.run(storage.save_upload(upload("lesson.txt", b"12345")))
