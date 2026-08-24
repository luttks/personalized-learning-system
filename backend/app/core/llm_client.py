"""Client LLM hợp nhất cho toàn bộ backend.

Trước đây có 2 cách gọi LLM song song, không dùng chung:
  - `exam_service._call_llm_with_fallback`: Gemini trước (xoay nhiều key) → fallback Groq (xoay nhiều key).
  - `understanding_agent.OpenAICompatibleProvider`: chỉ gọi 1 provider Groq/OpenAI-compatible, 1 key, không fallback.

Module này gộp lại thành một implementation duy nhất, dùng cho cả 2 kiểu gọi:
  - `complete_text(prompt, expect_json=...)`: nhận 1 prompt, trả về text thô (giữ hành vi cũ của
    `_call_llm_with_fallback`, dùng cho các hàm sinh nội dung trong `exam_service.py`).
  - `complete_json(system_prompt=, user_prompt=)`: khớp `ChatCompletionProvider` Protocol trong
    `understanding_agent.py`, dùng cho `LearnerUnderstandingAgent`, `diagnostic_question_generator`,
    `document_analyzer`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from functools import lru_cache
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE_SYSTEM_PROMPT = "Bạn là chuyên gia giáo dục AI."
_JSON_INSTRUCTION = " Trả về JSON hợp lệ, KHÔNG có markdown code block, KHÔNG có text thừa."
_GEMINI_MODELS = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
# Nhiều key Gemini xoay vòng CHỈ giúp khi lỗi mang tính cá nhân theo key (hết quota, rate limit, key
# bị thu hồi) — không giúp gì khi lỗi là 503 "model quá tải/không khả dụng" ở TẦNG MODEL (đã xác nhận
# lặp lại nhiều lần trong log thực tế cho đúng model "gemini-3.1-flash-lite"), vì lỗi đó xảy ra y hệt
# nhau với MỌI key gọi cùng model đó. "gemini-3.5-flash-lite" làm phương án 2 — khác model nên không
# chắc chắn cùng chịu ảnh hưởng bởi đúng sự cố đang khiến "gemini-3.1-flash-lite" quá tải.


class LLMClient:
    """Gemini trước (xoay nhiều key) → fallback Groq/OpenAI-compatible (xoay nhiều key)."""

    def __init__(
        self,
        *,
        gemini_api_keys: list[str],
        groq_api_keys: list[str],
        groq_base_url: str,
        groq_model: str,
        timeout_seconds: float = 45.0,
    ) -> None:
        self.gemini_api_keys = gemini_api_keys
        self.groq_api_keys = groq_api_keys
        self.groq_base_url = groq_base_url.rstrip("/")
        self.groq_model = groq_model
        self.timeout_seconds = timeout_seconds

    async def _call_gemini(
        self, user_content: str, system_prompt: str, api_key: str, expect_json: bool, max_tokens: int
    ) -> str:
        from google import genai  # type: ignore[import]
        from google.genai import errors  # type: ignore[import]

        client = genai.Client(api_key=api_key)
        sys_instruction = system_prompt + (_JSON_INSTRUCTION if expect_json else "")
        config = genai.types.GenerateContentConfig(
            system_instruction=sys_instruction, temperature=0.3, max_output_tokens=max_tokens
        )
        if expect_json:
            config.response_mime_type = "application/json"
        last_err: Exception | None = None
        for model_name in _GEMINI_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name, contents=user_content, config=config
                )
                if response and response.text:
                    return response.text
                raise RuntimeError("Phản hồi từ Gemini rỗng.")
            except errors.APIError as e:  # type: ignore[attr-defined]
                msg = str(e)
                if "API_KEY_INVALID" in msg or "API key not valid" in msg:
                    raise ValueError(f"GEMINI_API_KEY không hợp lệ: {msg[:100]}")
                logger.warning(f"Gemini model '{model_name}' lỗi ({msg[:80]}), thử model dự phòng...")
                last_err = e
            except Exception as e:
                logger.warning(f"Gemini model '{model_name}' lỗi ({str(e)[:80]}), thử model dự phòng...")
                last_err = e
        raise last_err or RuntimeError("Tất cả model Gemini đều thất bại.")

    async def _call_groq(
        self, user_content: str, system_prompt: str, api_key: str, expect_json: bool, max_tokens: int
    ) -> str:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self.groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt + (_JSON_INSTRUCTION if expect_json else ""),
                },
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        if expect_json:
            body["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(
                f"{self.groq_base_url}/chat/completions", headers=headers, json=body
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def complete_text(
        self,
        prompt: str,
        *,
        system_prompt: str = _BASE_SYSTEM_PROMPT,
        expect_json: bool = True,
        max_tokens: int = 8000,
    ) -> str:
        """Gemini trước (xoay key), fallback Groq (xoay key). Trả về text thô.

        `max_tokens` giới hạn ĐỘ DÀI PHẢN HỒI (không phải prompt đầu vào) — trước đây cố định 4000
        cho Groq bất kể call site nào, đã xác nhận qua thực tế: khi Gemini lỗi hàng loạt (503) và
        rơi xuống Groq, một phản hồi JSON lớn (VD nhiều giai đoạn/chủ đề của lộ trình) bị CẮT NGANG
        giữa chừng → JSON hỏng → parse thất bại/rỗng → toàn bộ cá nhân hóa (không chỉ location_page)
        bị mất, rơi về mẫu dự phòng thô sơ. Caller cho các bước sinh JSON lớn (khung lộ trình, lịch
        từng ngày) nên truyền max_tokens cao hơn giá trị mặc định."""
        last_err: Exception | None = None
        for i, key in enumerate(self.gemini_api_keys):
            try:
                result = await self._call_gemini(prompt, system_prompt, key, expect_json, max_tokens)
                logger.info(f"LLM rotation: thành công với Gemini key #{i + 1}")
                return result
            except Exception as e:
                logger.warning(f"Gemini key #{i + 1} lỗi: {str(e)[:80]}, thử tiếp...")
                last_err = e

        for i, key in enumerate(self.groq_api_keys):
            try:
                result = await self._call_groq(prompt, system_prompt, key, expect_json, max_tokens)
                logger.info(f"LLM rotation: thành công với Groq key #{i + 1}")
                return result
            except Exception as e:
                logger.warning(f"Groq key #{i + 1} lỗi: {str(e)[:80]}, thử tiếp...")
                last_err = e

        raise RuntimeError(f"Tất cả Gemini và Groq keys đều thất bại. Lỗi cuối: {last_err}")

    async def _call_gemini_embed(
        self, texts: list[str], task_type: str, api_key: str, output_dimensionality: int
    ) -> list[list[float]]:
        from google import genai  # type: ignore[import]
        from google.genai import errors  # type: ignore[import]

        client = genai.Client(api_key=api_key)
        config = genai.types.EmbedContentConfig(
            task_type=task_type, output_dimensionality=output_dimensionality
        )
        try:
            response = await client.aio.models.embed_content(
                model=settings.gemini_embedding_model, contents=texts, config=config
            )
            if not response or not response.embeddings:
                raise RuntimeError("Phản hồi embedding từ Gemini rỗng.")
            return [e.values for e in response.embeddings]
        except errors.APIError as e:  # type: ignore[attr-defined]
            msg = str(e)
            if "API_KEY_INVALID" in msg or "API key not valid" in msg:
                raise ValueError(f"GEMINI_API_KEY không hợp lệ: {msg[:100]}")
            raise

    async def _embed_batch_with_retry(
        self, batch: list[str], task_type: str, output_dimensionality: int, max_attempts: int = 4
    ) -> list[list[float]]:
        """Thử TOÀN BỘ self.gemini_api_keys cho 1 batch; nếu cả loạt key đều lỗi, nghỉ (backoff
        tăng dần: 10s, 20s, 30s...) rồi thử lại nguyên vòng — KHÔNG bỏ cuộc ngay sau vòng key đầu
        tiên. Cần thiết vì đã xác nhận qua thực tế: cả 3 key cùng bị 429 RESOURCE_EXHAUSTED ngay ở
        batch đầu tiên dù 2/3 key chưa từng gọi trước đó trong lần chạy này — cho thấy hạn mức RẤT
        CÓ THỂ dùng chung ở cấp dự án (project) chứ không tách riêng theo từng key, nên xoay key
        không đủ để vượt qua 429 — phải nghỉ thật sự."""
        last_err: Exception | None = None
        for attempt in range(max_attempts):
            for i, key in enumerate(self.gemini_api_keys):
                try:
                    vectors = await self._call_gemini_embed(batch, task_type, key, output_dimensionality)
                    logger.info(f"Embedding: thành công với Gemini key #{i + 1} (lượt thử {attempt + 1})")
                    return vectors
                except Exception as e:
                    logger.warning(f"Gemini key #{i + 1} lỗi khi embed: {str(e)[:80]}")
                    last_err = e
            if attempt < max_attempts - 1:
                backoff = 10 * (attempt + 1)
                logger.warning(f"Toàn bộ key đều lỗi ở lượt thử {attempt + 1}, nghỉ {backoff}s rồi thử lại...")
                await asyncio.sleep(backoff)
        raise RuntimeError(
            f"Tất cả Gemini keys đều thất bại khi tạo embedding sau {max_attempts} lượt thử. Lỗi cuối: {last_err}"
        )

    async def embed_texts(
        self,
        texts: list[str],
        *,
        task_type: str,
        output_dimensionality: int = 768,
        batch_size: int = 50,
        batch_delay_seconds: float = 3.0,
    ) -> list[list[float]]:
        """Xoay vòng self.gemini_api_keys (KHÔNG fallback Groq — không có embedding dùng ở đây),
        batch nội bộ `batch_size` văn bản/lần gọi (đã kiểm chứng thật: 50 văn bản/lần, ~1.7s,
        không lỗi khi gọi ĐƠN LẺ — không phải số đoán). `batch_delay_seconds`: nghỉ giữa 2 batch
        liên tiếp để không dồn dập vượt hạn mức RPM của Gemini embedding — đã xác nhận qua thực
        tế: gọi liên tiếp không nghỉ giữa nhiều batch khiến toàn bộ key bị 429 RESOURCE_EXHAUSTED
        (xem `_embed_batch_with_retry`). `task_type`: 'RETRIEVAL_DOCUMENT' lúc đánh chỉ mục tài
        liệu, 'RETRIEVAL_QUERY' lúc truy hồi — đúng khuyến nghị embedding bất đối xứng của Gemini
        cho use-case tìm kiếm."""
        if not texts:
            return []
        all_vectors: list[list[float]] = []
        for batch_num, start in enumerate(range(0, len(texts), batch_size)):
            if batch_num > 0 and batch_delay_seconds > 0:
                await asyncio.sleep(batch_delay_seconds)
            batch = texts[start : start + batch_size]
            vectors = await self._embed_batch_with_retry(batch, task_type, output_dimensionality)
            all_vectors.extend(vectors)
        return all_vectors

    async def complete_json(
        self, *, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        """Khớp `ChatCompletionProvider` Protocol (dùng bởi LearnerUnderstandingAgent, v.v.)."""
        raw = await self.complete_text(
            user_prompt, system_prompt=system_prompt, expect_json=True
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))


@lru_cache
def get_llm_client() -> LLMClient:
    return LLMClient(
        gemini_api_keys=settings.gemini_api_keys,
        groq_api_keys=settings.llm_api_keys,
        groq_base_url=settings.llm_base_url,
        groq_model=settings.llm_model or "",
        timeout_seconds=settings.llm_timeout_seconds,
    )
