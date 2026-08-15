import io
import zipfile

from app.services.exam_service import build_learning_document_content, read_text_document


def test_read_text_document_extracts_docx_paragraphs_and_tables() -> None:
    document_xml = """<?xml version='1.0' encoding='UTF-8'?>
    <w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
      <w:body>
        <w:p><w:r><w:t>Bài 1. Các cuộc cách mạng tư sản ở châu Âu và Bắc Mỹ</w:t></w:r></w:p>
        <w:p><w:r><w:t>Nguyên nhân và diễn biến.</w:t></w:r></w:p>
        <w:tbl>
          <w:tr><w:tc><w:p><w:r><w:t>Anh</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>1640</w:t></w:r></w:p></w:tc></w:tr>
        </w:tbl>
      </w:body>
    </w:document>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    text = read_text_document(buffer.getvalue(), ".docx")

    assert "Bài 1. Các cuộc cách mạng tư sản ở châu Âu và Bắc Mỹ" in text
    assert "Nguyên nhân và diễn biến." in text
    assert "[BẢNG] Anh | 1640" in text


def test_read_text_document_rejects_legacy_doc() -> None:
    try:
        read_text_document(b"legacy", ".doc")
    except ValueError as error:
        assert ".docx" in str(error)
    else:
        raise AssertionError("legacy .doc must not be treated as readable text")


def test_learning_document_highlights_keep_verified_source_refs() -> None:
    text = (
        "Bài 1. Cách mạng tư sản Anh\n\n"
        "Nguyên nhân kinh tế và xã hội là kiến thức trọng tâm cần nắm vững.\n\n"
        "Diễn biến và kết quả của cuộc cách mạng."
    )
    blocks, highlights = build_learning_document_content(
        text,
        topics=["Cách mạng tư sản Anh"],
        key_passages=[{
            "concept": "Nguyên nhân",
            "importance": "must_learn",
            "quote": "Nguyên nhân kinh tế và xã hội là kiến thức trọng tâm cần nắm vững.",
            "reason": "Nền tảng của bài học",
        }],
    )

    assert blocks[0]["type"] == "heading"
    assert highlights
    assert all(
        evidence["block_id"] in {block["id"] for block in blocks}
        for highlight in highlights
        for evidence in highlight["evidence"]
    )
