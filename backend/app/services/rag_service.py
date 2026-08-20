import hashlib
import logging
import math
import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.content_catalog import CourseChapter
from app.models.content_chunk import ContentChunk
from app.models.document_analysis import DocumentAnalysis
from app.models.user import User
from app.services.content_service import CourseNotFoundError, get_analysis_for_manager

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 768
GEMINI_EMBEDDING_MODEL = "gemini-text-embedding-004"
FALLBACK_EMBEDDING_MODEL = "local-feature-hash-v1"
PAGE_MARKER = re.compile(r"^\s*\[(?:Trang|Page)\s+(\d+)\]\s*$", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    page_number: int | None


def feature_hash_embedding(text: str) -> list[float]:
    """Embedding cục bộ dạng feature-hashing (blake2b) — dùng làm fallback khi không có
    Gemini key hoặc API lỗi, và cho test không cần gọi mạng."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    normalized = unicodedata.normalize("NFKC", text).casefold()
    tokens = TOKEN_PATTERN.findall(normalized)
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        index = value % EMBEDDING_DIMENSIONS
        vector[index] += -1.0 if value & 1 else 1.0
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude:
        return [value / magnitude for value in vector]
    return vector


def _gemini_embedding(text: str, api_key: str) -> list[float]:
    from google import genai  # type: ignore[import]

    client = genai.Client(api_key=api_key)
    result = client.models.embed_content(model="models/text-embedding-004", contents=text)
    values = list(result.embeddings[0].values)
    if len(values) != EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"Gemini embedding trả về {len(values)} chiều, kỳ vọng {EMBEDDING_DIMENSIONS}."
        )
    return values


def embed_text(text: str) -> tuple[list[float], str]:
    """Sinh embedding thật qua Gemini Embedding API (xoay nhiều key); nếu không có key
    hoặc tất cả đều lỗi, fallback về feature-hashing cục bộ. Trả về (vector, embedding_model)."""
    for i, key in enumerate(settings.gemini_api_keys):
        try:
            vector = _gemini_embedding(text, key)
            return vector, GEMINI_EMBEDDING_MODEL
        except Exception as e:
            logger.warning(f"Gemini embedding key #{i + 1} lỗi: {str(e)[:80]}, thử tiếp...")
    logger.warning("Không có Gemini key khả dụng cho embedding, dùng fallback feature-hashing.")
    return feature_hash_embedding(text), FALLBACK_EMBEDDING_MODEL


def split_content_chunks(
    text: str,
    *,
    max_characters: int = 1200,
    overlap_characters: int = 160,
) -> list[ChunkDraft]:
    paragraphs: list[tuple[str, int | None]] = []
    current_page: int | None = None
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        marker = PAGE_MARKER.match(lines[0])
        if marker:
            current_page = int(marker.group(1))
            block = "\n".join(lines[1:]).strip()
        if block:
            paragraphs.append((block, current_page))

    chunks: list[ChunkDraft] = []
    buffer = ""
    buffer_page: int | None = None
    for paragraph, page in paragraphs:
        parts = _split_long_text(paragraph, max_characters)
        for part in parts:
            candidate = f"{buffer}\n\n{part}".strip() if buffer else part
            if buffer and len(candidate) > max_characters:
                chunks.append(ChunkDraft(buffer, buffer_page))
                overlap = (
                    buffer[-overlap_characters:].strip()
                    if overlap_characters > 0
                    else ""
                )
                buffer = f"{overlap}\n\n{part}".strip() if overlap else part
                buffer_page = page
            else:
                buffer = candidate
                buffer_page = buffer_page if buffer_page is not None else page
    if buffer:
        chunks.append(ChunkDraft(buffer, buffer_page))
    return chunks


def _split_long_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > limit:
            if current:
                result.append(current)
                current = ""
            result.extend(
                sentence[start : start + limit]
                for start in range(0, len(sentence), limit)
            )
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > limit:
            result.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        result.append(current)
    return result


async def rebuild_content_index(
    session: AsyncSession,
    user: User,
    course_version_id: UUID,
) -> list[ContentChunk]:
    analysis = await get_analysis_for_manager(session, user, course_version_id)
    if analysis is None or analysis.status != "completed":
        raise CourseNotFoundError
    return await _replace_chunks(session, analysis)


async def rebuild_content_index_for_analysis(
    session: AsyncSession,
    analysis: DocumentAnalysis,
) -> list[ContentChunk]:
    return await _replace_chunks(session, analysis)


async def _replace_chunks(
    session: AsyncSession,
    analysis: DocumentAnalysis,
) -> list[ContentChunk]:
    source_text = analysis.edited_text or analysis.extracted_text
    drafts = split_content_chunks(source_text)
    await session.execute(
        delete(CourseChapter).where(
            CourseChapter.course_version_id == analysis.course_version_id
        )
    )
    await session.execute(
        delete(ContentChunk).where(
            ContentChunk.course_version_id == analysis.course_version_id
        )
    )
    chunks = []
    for index, draft in enumerate(drafts):
        vector, embedding_model = embed_text(draft.text)
        chunks.append(
            ContentChunk(
                course_version_id=analysis.course_version_id,
                document_id=analysis.document_id,
                chunk_index=index,
                text=draft.text,
                character_count=len(draft.text),
                token_count=len(TOKEN_PATTERN.findall(draft.text)),
                page_number=draft.page_number,
                source_label=(
                    f"Trang {draft.page_number}" if draft.page_number else f"Đoạn {index + 1}"
                ),
                metadata_json={"source": "edited" if analysis.edited_text else "original"},
                embedding_model=embedding_model,
                embedding=vector,
            )
        )
    session.add_all(chunks)
    await session.commit()
    for chunk in chunks:
        await session.refresh(chunk)
    return chunks


async def search_content_chunks(
    session: AsyncSession,
    user: User,
    course_version_id: UUID,
    query: str,
    limit: int,
) -> list[tuple[ContentChunk, float, float]]:
    await get_analysis_for_manager(session, user, course_version_id)
    query_embedding, _ = embed_text(query)
    vector_score = 1 - ContentChunk.embedding.cosine_distance(query_embedding)
    lexical_score = func.ts_rank_cd(
        func.to_tsvector("simple", ContentChunk.text),
        func.plainto_tsquery("simple", query),
    )
    combined_score = vector_score * 0.75 + lexical_score * 0.25
    rows = await session.execute(
        select(ContentChunk, vector_score, combined_score)
        .where(ContentChunk.course_version_id == course_version_id)
        .order_by(combined_score.desc())
        .limit(limit)
    )
    return [
        (chunk, float(cosine or 0), float(score or 0))
        for chunk, cosine, score in rows.all()
    ]


async def content_index_count(
    session: AsyncSession,
    user: User,
    course_version_id: UUID,
) -> int:
    await get_analysis_for_manager(session, user, course_version_id)
    return int(
        await session.scalar(
            select(func.count(ContentChunk.id)).where(
                ContentChunk.course_version_id == course_version_id
            )
        )
        or 0
    )
