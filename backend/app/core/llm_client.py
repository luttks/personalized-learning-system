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
_GEMINI_MODELS = ["gemini-3.1-flash-lite"]


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
        self, user_content: str, system_prompt: str, api_key: str, expect_json: bool
    ) -> str:
        from google import genai  # type: ignore[import]
        from google.genai import errors  # type: ignore[import]

        client = genai.Client(api_key=api_key)
        sys_instruction = system_prompt + (_JSON_INSTRUCTION if expect_json else "")
        config = genai.types.GenerateContentConfig(
            system_instruction=sys_instruction, temperature=0.3
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
        self, user_content: str, system_prompt: str, api_key: str, expect_json: bool
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
            "max_tokens": 4000,
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
    ) -> str:
        """Gemini trước (xoay key), fallback Groq (xoay key). Trả về text thô."""
        last_err: Exception | None = None
        for i, key in enumerate(self.gemini_api_keys):
            try:
                result = await self._call_gemini(prompt, system_prompt, key, expect_json)
                logger.info(f"LLM rotation: thành công với Gemini key #{i + 1}")
                return result
            except Exception as e:
                logger.warning(f"Gemini key #{i + 1} lỗi: {str(e)[:80]}, thử tiếp...")
                last_err = e

        for i, key in enumerate(self.groq_api_keys):
            try:
                result = await self._call_groq(prompt, system_prompt, key, expect_json)
                logger.info(f"LLM rotation: thành công với Groq key #{i + 1}")
                return result
            except Exception as e:
                logger.warning(f"Groq key #{i + 1} lỗi: {str(e)[:80]}, thử tiếp...")
                last_err = e

        raise RuntimeError(f"Tất cả Gemini và Groq keys đều thất bại. Lỗi cuối: {last_err}")

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
