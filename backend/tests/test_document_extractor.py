import zipfile

import fitz
from app.services import document_extractor
from app.services.document_extractor import (
    OcrOptions,
    _lines_from_ocr_data,
    extract_text,
    fallback_structure,
)


def test_extracts_utf8_text_and_builds_chapters(tmp_path) -> None:
    path = tmp_path / "history.txt"
    path.write_text(
        "Lịch sử 8\nChương 1: Thời cận đại\nSự hình thành xã hội mới.\n"
        "Chương 2: Cách mạng công nghiệp\nMáy hơi nước thay đổi sản xuất.",
        encoding="utf-8",
    )

    text = extract_text(path, "text/plain", max_chars=10_000)
    structure = fallback_structure(text, "Lịch sử 8")

    assert "Cách mạng công nghiệp" in text
    assert len(structure.chapters) == 2
    assert structure.chapters[0].title.startswith("Chương 1")


def test_extracts_docx_xml_text(tmp_path) -> None:
    path = tmp_path / "lesson.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            "<w:document xmlns:w='urn:w'><w:body><w:p>"
            "<w:r><w:t>Chương 1: Đại số</w:t></w:r>"
            "</w:p></w:body></w:document>",
        )

    text = extract_text(
        path,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        max_chars=10_000,
    )

    assert text == "Chương 1: Đại số"


def test_extraction_respects_character_limit(tmp_path) -> None:
    path = tmp_path / "large.txt"
    path.write_text("a" * 1000, encoding="utf-8")

    assert len(extract_text(path, "text/plain", max_chars=120)) == 120


def test_scanned_pdf_uses_ocr(monkeypatch, tmp_path) -> None:
    path = tmp_path / "scanned.pdf"
    with fitz.open() as document:
        document.new_page()
        document.save(path)
    monkeypatch.setattr(
        document_extractor,
        "_ocr_image",
        lambda image, languages, min_confidence: "Chương 1: Việt Nam thế kỷ XIX",
    )

    text = extract_text(
        path,
        "application/pdf",
        max_chars=10_000,
        ocr=OcrOptions(),
    )

    assert "[Trang 1]" in text
    assert "Việt Nam thế kỷ XIX" in text


def test_pdf_text_layer_does_not_use_ocr(monkeypatch, tmp_path) -> None:
    path = tmp_path / "text.pdf"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "Chapter 1: Existing searchable text in this PDF")
        document.save(path)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("OCR should not run for a usable text layer")

    monkeypatch.setattr(document_extractor, "_ocr_image", fail_if_called)
    text = extract_text(path, "application/pdf", max_chars=10_000)

    assert "Existing searchable text" in text


def test_ocr_lines_are_sorted_top_down_and_low_confidence_noise_is_removed() -> None:
    data = {
        "text": ["dưới", "NHIỄU", "Dòng", "trên"],
        "conf": ["92", "12", "96", "94"],
        "block_num": [2, 3, 1, 1],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 1, 1],
        "top": [220, 150, 40, 40],
        "left": [30, 10, 20, 90],
    }

    text = _lines_from_ocr_data(data, min_confidence=35)

    assert text == "Dòng trên\ndưới"
    assert "NHIỄU" not in text


def test_ocr_finishes_one_layout_block_before_the_next() -> None:
    data = {
        "text": ["Trái-1", "Phải-1", "Trái-2"],
        "conf": ["95", "95", "95"],
        "block_num": [1, 2, 1],
        "par_num": [1, 1, 1],
        "line_num": [1, 1, 2],
        "top": [40, 40, 90],
        "left": [20, 500, 20],
    }

    text = _lines_from_ocr_data(data, min_confidence=35)

    assert text == "Trái-1\nTrái-2\nPhải-1"
