"""
Exam Parser Service — parse Markdown/LaTeX exam text into structured questions.

Ported from WorkFlow/parser.py.
"""

import re
from typing import Any


def auto_format_math_latex(text: str) -> str:
    r"""
    Normalise LaTeX delimiters from various OCR sources.

    Conversions:
      - ``\( ... \)``  →  ``$ ... $``   (inline)
      - ``\[ ... \]``  →  ``$$ ... $$`` (display)
      - Existing ``$ ... $`` and ``$$ ... $$`` are left unchanged.
    """
    if not text:
        return ""
    text = text.replace(r"\\(", "$").replace(r"\\)", "$")
    text = text.replace(r"\\\[", "$$").replace(r"\\\]", "$$")
    text = text.replace(r"\(", "$").replace(r"\)", "$")
    text = text.replace(r"\[", "$$").replace(r"\]", "$$")
    return text


def parse_exam_questions(text: str) -> dict[str, Any]:
    """
    Parse Markdown/LaTeX text into a hierarchical exam structure.

    Supports:
      - Texts with headings like ``Câu I / Câu II / Bài 1 / Bài 2…``
      - Free-form text (no question headings) → returned as a single block
    """
    text_clean = auto_format_math_latex(text)

    lines = text_clean.split("\n")
    header_lines: list[str] = []
    questions: list[dict[str, Any]] = []

    # Pattern to recognise question headings
    question_pattern = re.compile(
        r"^(Câu|Bài)\s+([IVXLCDM0-9]+)[:\.]?\s*(?:\(([^)]+)\))?",
        re.IGNORECASE,
    )

    # Pattern for scores: (2,0 điểm), 3 điểm, 0.5đ, …
    points_pattern = re.compile(
        r"\(?\s*([0-9]+[,\.][0-9]+\s*điểm|[0-9]+\s*đ(?:iểm)?)\s*\)?",
        re.IGNORECASE,
    )

    current_q: dict[str, Any] | None = None

    for line in lines:
        raw_stripped = line.strip()
        # Strip markdown markers for pattern matching
        clean_line = re.sub(r"[#*_]", "", raw_stripped).strip()
        match = question_pattern.search(clean_line)

        if match:
            if current_q:
                current_q["content"] = current_q["content"].strip()
                questions.append(current_q)

            q_prefix = match.group(1).capitalize()
            q_num = match.group(2).upper()

            q_points = match.group(3).strip() if match.group(3) else ""
            if not q_points:
                pts_match = points_pattern.search(clean_line)
                if pts_match:
                    q_points = pts_match.group(1)

            q_id = f"{q_prefix} {q_num}"

            current_q = {
                "id": q_id,
                "title": clean_line,
                "points": q_points,
                "content": "",
                "sub_questions": [],
            }
        else:
            if current_q is None:
                header_lines.append(line)
            else:
                current_q["content"] += line + "\n"

    # Flush the last question
    if current_q:
        current_q["content"] = current_q["content"].strip()
        questions.append(current_q)

    # Fallback: if no questions were detected, wrap everything as one block
    if not questions and text_clean.strip():
        questions = [
            {
                "id": "Nội dung",
                "title": "Nội dung tài liệu",
                "points": "",
                "content": text_clean.strip(),
                "sub_questions": [],
            }
        ]

    # Extract sub-questions (1), 2), a., b., …)
    sub_pattern = re.compile(
        r"^\s*([1-9]\d*|[a-z])[)\.][ \t]+(.*)",
        re.MULTILINE,
    )
    for q in questions:
        sub_matches = sub_pattern.findall(q["content"])
        if sub_matches:
            q["sub_questions"] = [
                {"label": m[0], "text": m[1].strip()} for m in sub_matches
            ]

    header_text = "\n".join(header_lines).strip()

    # Count all LaTeX formulas (inline + display)
    math_formulas = re.findall(
        r"\$\$[\s\S]*?\$\$|\$[^$\n]+?\$",
        text_clean,
    )

    return {
        "header": header_text,
        "question_count": len(questions),
        "formula_count": len(math_formulas),
        "questions": questions,
        "raw_markdown": text_clean,
    }
