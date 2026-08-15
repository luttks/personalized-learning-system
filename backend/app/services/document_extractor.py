import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import fitz
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pytesseract import Output

from app.schemas.content import AnalysisChapter, DocumentStructure


class DocumentExtractionError(Exception):
    pass


@dataclass(frozen=True)
class OcrOptions:
    enabled: bool = True
    languages: str = "vie+eng"
    dpi: int = 150
    max_pages: int = 400
    min_text_chars: int = 40
    min_confidence: int = 35


def extract_text(
    path: str | Path,
    content_type: str,
    max_chars: int,
    *,
    ocr: OcrOptions | None = None,
) -> str:
    file_path = Path(path)
    options = ocr or OcrOptions()
    try:
        if content_type == "application/pdf":
            text = _extract_pdf(file_path, max_chars, options)
        elif content_type == "text/plain":
            text = file_path.read_text(encoding="utf-8-sig")
        elif content_type.endswith(
            ("wordprocessingml.document", "presentationml.presentation")
        ):
            text = _extract_open_xml(file_path, "t")
        elif content_type in {"image/png", "image/jpeg"}:
            if not options.enabled:
                raise DocumentExtractionError("OCR đang bị tắt nên không thể đọc tài liệu ảnh.")
            with Image.open(file_path) as image:
                text = _ocr_image(
                    image,
                    options.languages,
                    options.min_confidence,
                )
        else:
            raise DocumentExtractionError("Định dạng tài liệu chưa được hỗ trợ.")
    except DocumentExtractionError:
        raise
    except (OSError, ValueError, zipfile.BadZipFile, fitz.FileDataError) as error:
        raise DocumentExtractionError("Không thể đọc nội dung tài liệu.") from error

    normalized = _normalize_text(text)
    if not normalized:
        raise DocumentExtractionError("Tài liệu không có nội dung văn bản để phân tích.")
    return normalized[:max_chars]


def _extract_pdf(path: Path, max_chars: int, options: OcrOptions) -> str:
    parts: list[str] = []
    character_count = 0
    with fitz.open(path) as document:
        page_count = min(document.page_count, options.max_pages)
        for page_index in range(page_count):
            page = document.load_page(page_index)
            page_text = page.get_text("text").strip()
            if len(page_text) < options.min_text_chars and options.enabled:
                scale = options.dpi / 72
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                with Image.open(io.BytesIO(pixmap.tobytes("png"))) as image:
                    ocr_text = _ocr_image(
                        image,
                        options.languages,
                        options.min_confidence,
                    ).strip()
                if len(ocr_text) > len(page_text):
                    page_text = ocr_text
            if page_text:
                page_part = f"[Trang {page_index + 1}]\n{page_text}"
                parts.append(page_part)
                character_count += len(page_part)
            if character_count >= max_chars:
                break
    return "\n\n".join(parts)


def _ocr_image(
    image: Image.Image,
    languages: str,
    min_confidence: int = 35,
) -> str:
    try:
        prepared = _prepare_ocr_image(image)
        data = pytesseract.image_to_data(
            prepared,
            lang=languages,
            config="--oem 1 --psm 3 -c preserve_interword_spaces=1",
            output_type=Output.DICT,
        )
        return _lines_from_ocr_data(data, min_confidence)
    except pytesseract.TesseractNotFoundError as error:
        raise DocumentExtractionError("Máy chủ chưa cài đặt Tesseract OCR.") from error
    except pytesseract.TesseractError as error:
        raise DocumentExtractionError(
            f"OCR thất bại. Hãy kiểm tra bộ ngôn ngữ '{languages}'."
        ) from error


def _prepare_ocr_image(image: Image.Image) -> Image.Image:
    grayscale = ImageOps.grayscale(image)
    contrasted = ImageOps.autocontrast(grayscale, cutoff=1)
    return ImageEnhance.Contrast(contrasted).enhance(1.15).filter(
        ImageFilter.SHARPEN
    )


def _lines_from_ocr_data(data: dict, min_confidence: int) -> str:
    lines: dict[tuple[int, int, int], dict[str, object]] = {}
    word_count = len(data.get("text", []))
    for index in range(word_count):
        word = str(data["text"][index]).strip()
        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            continue
        if confidence < min_confidence or not re.search(r"\w", word, re.UNICODE):
            continue
        key = (
            int(data["block_num"][index]),
            int(data["par_num"][index]),
            int(data["line_num"][index]),
        )
        line = lines.setdefault(
            key,
            {
                "block": int(data["block_num"][index]),
                "top": int(data["top"][index]),
                "left": int(data["left"][index]),
                "words": [],
            },
        )
        line["top"] = min(int(line["top"]), int(data["top"][index]))
        line["left"] = min(int(line["left"]), int(data["left"][index]))
        line["words"].append((int(data["left"][index]), word))

    ordered_lines = sorted(
        lines.values(),
        key=lambda line: (line["block"], line["top"], line["left"]),
    )
    return "\n".join(
        " ".join(word for _, word in sorted(line["words"]))
        for line in ordered_lines
        if line["words"]
    )


def fallback_structure(text: str, title: str) -> DocumentStructure:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    heading_pattern = re.compile(
        r"^(?:chương|chapter|phần|part)\s+([\w.-]+)\s*[:.-]?\s*(.*)$",
        re.IGNORECASE,
    )
    headings: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if heading_pattern.match(line):
            headings.append((index, line))

    if not headings:
        block_size = max(1, len(lines) // 5)
        headings = [(index, f"Phần {position + 1}") for position, index in enumerate(range(0, len(lines), block_size))]

    chapters: list[AnalysisChapter] = []
    for position, (start, heading) in enumerate(headings, start=1):
        end = headings[position][0] if position < len(headings) else len(lines)
        body = " ".join(lines[start + 1:end])
        if heading.startswith("Phần "):
            body = " ".join(lines[start:end])
        points = [line for line in lines[start + 1:end] if len(line) > 25][:5]
        chapters.append(
            AnalysisChapter(
                number=position,
                title=heading[:255],
                summary=(body[:700] or "Chưa có phần tóm tắt tự động.").strip(),
                key_points=[point[:255] for point in points],
            )
        )
    return DocumentStructure(
        title=title,
        summary=" ".join(lines)[:1200],
        chapters=chapters[:30],
        source="fallback",
    )


def _extract_open_xml(path: Path, tag: str) -> str:
    values: list[str] = []
    with zipfile.ZipFile(path) as archive:
        xml_name = (
            "word/document.xml"
            if path.suffix.lower() == ".docx"
            else "ppt/presentation.xml"
        )
        names = [xml_name] if tag == "t" else archive.namelist()
        for name in names:
            if not name.endswith(".xml") or name not in archive.namelist():
                continue
            root = ElementTree.fromstring(archive.read(name))
            local = lambda node: node.tag.rsplit("}", 1)[-1]

            def text_in(element: ElementTree.Element) -> str:
                parts: list[str] = []
                for node in element.iter():
                    node_name = local(node)
                    if node_name == tag:
                        parts.append(node.text or "")
                    elif node_name in {"tab", "br", "cr"}:
                        parts.append("\t" if node_name == "tab" else "\n")
                return "".join(parts).strip()

            def collect(container: ElementTree.Element) -> None:
                for node in container:
                    node_name = local(node)
                    if node_name == "p":
                        value = text_in(node)
                        if value:
                            values.append(value)
                    elif node_name == "tbl":
                        for row in node.iter():
                            if local(row) != "tr":
                                continue
                            cells = [text_in(cell) for cell in row if local(cell) == "tc"]
                            cells = [cell for cell in cells if cell]
                            if cells:
                                values.append("[BẢNG] " + " | ".join(cells))
                    else:
                        collect(node)

            if tag == "t" and local(root) in {"document", "body"}:
                collect(root)
            elif tag != "t":
                values.extend(node.text or "" for node in root.iter() if local(node) == tag)
    return "\n".join(values)


def _normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
