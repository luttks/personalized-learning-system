# HƯỚNG DẪN CHI TIẾT GỘP DỰ ÁN WORKFLOW VÀO PERSONALIZED-LEARNING-SYSTEM (MERGE.MD)

Tài liệu này trình bày chi tiết kiến trúc, giải pháp và quy trình từng bước để gộp dự án **WorkFlow** (mô hình FastAPI + Jinja2 HTML đơn lẻ) vào dự án **Personalized-Learning-System** (kiến trúc Microservices gồm React 19 Frontend + FastAPI Async Backend + Celery Worker + PostgreSQL/pgvector + Redis + Docker Compose).

---

## 1. TỔNG QUAN VỀ KIẾN TRÚC VÀ CHIẾN LƯỢC GỘP

### 1.1 Hiện trạng của 2 dự án

| Đặc tính | Dự án WorkFlow (`d:\intern\WorkFlow`) | Dự án Personalized (`d:\intern\personalized-learning-system`) |
| :--- | :--- | :--- |
| **Kiến trúc** | FastAPI Monolith (SSR Jinja2 HTML templates) | Decoupled SPA + Microservices (React Frontend + FastAPI Backend) |
| **Giao diện (UI)** | HTML/CSS/JS thuần trong `templates/` | React 19 + TypeScript + Vite + Tailwind CSS v4 + Lucide Icons |
| **Tính năng chính** | OCR Đề thi/Bảng điểm bằng Gemini API, bóc tách LaTeX toán học, parser câu hỏi, crawler SGK | Quản lý khóa học, lộ trình học tập cá nhân hóa, chẩn đoán năng lực, quản lý học viên |
| **Môi trường chạy** | `uvicorn app:app` chạy trực tiếp với `.env` local | Containerized hoàn toàn qua `docker-compose.yml` (Postgres, Redis, Backend, Worker, Frontend) |

### 1.2 Chiến lược tích hợp chuẩn (Standard Merge Strategy)

1. **Backend Integration**: 
   - Đưa toàn bộ xử lý OCR (`run_gemini_ocr`), bóc tách câu hỏi (`parser.py`) và crawler (`crawler_service.py`) từ WorkFlow về làm **Services** trong `backend/app/services/` của Personalized.
   - Tạo REST API Router mới `backend/app/api/v1/routes/exam_workflow.py` thay thế các SSR endpoint Jinja2.
   - Tích hợp công việc OCR nặng vào Celery Worker (`backend/app/worker/`) nếu xử lý tài liệu lớn hoặc chạy async.

2. **Frontend UI Alignment**:
   - Chuyển toàn bộ giao diện HTML Jinja2 (`templates/index.html`) thành React Component `frontend/src/pages/ExamWorkflowPage.tsx` và các component con trong `frontend/src/components/workflow/`.
   - Đồng nhất UI với Design System của Personalized: Dark/Light Mode, Tailwind v4, Lucide Icons, React Query để call API, hỗ trợ KaTeX/LaTeX render trực quan.

3. **Docker & Dependency Consolidation**:
   - Hợp nhất tất cả thư viện Python từ WorkFlow (`google-genai`, `openai`, `beautifulsoup4`, `python-docx`) vào `backend/requirements.txt`.
   - Cập nhật `backend/Dockerfile` cài đặt đầy đủ các package hệ thống OS (`poppler-utils` cho PDF, `tesseract-ocr`, `libpq-dev`).
   - Cập nhật `docker-compose.yml` và `.env` để truyền các API Key (`GEMINI_API_KEY`, `OPENAI_API_KEY`) sang container.

---

## 2. HỢP NHẤT DEPENDENCIES VÀ CẤU HÌNH DOCKER BUILD

### 2.1 Cập nhật `backend/requirements.txt`

Thêm các thư viện cần thiết của WorkFlow vào `backend/requirements.txt` của Personalized:

```txt
# --- Gốc của Personalized Learning System ---
fastapi[standard]>=0.115,<1.0
uvicorn[standard]>=0.30,<1.0

sqlalchemy[asyncio]>=2.0,<2.1
asyncpg>=0.30,<1.0
psycopg[binary]>=3.2,<4.0
alembic>=1.14,<2.0
pgvector>=0.3,<1.0

pydantic>=2.10,<3.0
pydantic-settings>=2.7,<3.0
email-validator>=2.2,<3.0

PyJWT>=2.10,<3.0
pwdlib[argon2]>=0.2,<1.0
python-multipart>=0.0.20,<1.0

celery[redis]>=5.6,<5.7
redis>=5.2,<6.0

httpx>=0.28,<1.0
pypdf>=5.0,<7.0
PyMuPDF>=1.24,<2.0
pytesseract>=0.3.13,<1.0
Pillow>=11,<13

pytest>=8.3,<9.0
pytest-asyncio>=0.25,<1.0
ruff>=0.9,<1.0

# --- Bổ sung từ WorkFlow ---
google-genai>=1.0.0
openai>=1.0.0
beautifulsoup4>=4.12.0
python-docx>=1.1.0
```

> **Lưu ý quan trọng**: Dự án WorkFlow dùng SDK `google-genai` mới (thay thế cho SDK cũ `google-generativeai`). Đảm bảo giữ đúng `google-genai>=1.0.0`.

### 2.2 Cập nhật `backend/Dockerfile`

Để xử lý bóc tách PDF, file Word (`.docx`), và OCR bằng Tesseract/Gemini, container `backend` cần bổ sung package `poppler-utils` (cho PyMuPDF/pdf2image) và các công cụ biên dịch:

```dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# Cài đặt các gói hệ thống cần thiết cho PostgreSQL, OCR, PDF processing và python-docx
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-vie \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.3 Cập nhật `frontend/package.json`

Thêm các package hỗ trợ render LaTeX công thức toán học (`katex`, `rehype-katex`, `remark-math`, `react-markdown`) vào frontend để hiển thị đề thi toán học từ WorkFlow:

```json
{
  "dependencies": {
    "katex": "^0.16.11",
    "react-katex": "^3.0.1",
    "react-markdown": "^9.0.1",
    "remark-math": "^6.0.0",
    "rehype-katex": "^7.0.0"
  }
}
```

### 2.4 Cập nhật Biến Môi Trường (`.env` & `.env.example`)

Bổ sung các khóa API của WorkFlow vào file `.env` của `personalized-learning-system`:

```env
# Gemini API Key cho OCR & Parser Đề thi / Bảng điểm
GEMINI_API_KEY=your_gemini_api_key_here

# OpenAI API Key (nếu sử dụng fallback GPT-4o cho OCR)
OPENAI_API_KEY=your_openai_api_key_here

# Thư mục lưu trữ tạm thời cho file Upload
UPLOAD_DIR=uploads
```

### 2.5 Cập nhật `docker-compose.yml`

Đảm bảo container `backend` và `worker` có truy cập vào `GEMINI_API_KEY` và mounted volume `./uploads`:

```yaml
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: learning-backend
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "${BACKEND_PORT}:8000"
    volumes:
      - ./backend:/app
      - ./uploads:/app/uploads
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: >
      sh -c "alembic upgrade head &&
      exec uvicorn app.main:app
      --host 0.0.0.0
      --port 8000
      --reload"

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: learning-worker
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./backend:/app
      - ./uploads:/app/uploads
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: >
      celery
      -A app.worker.celery_app:celery_app
      worker
      --loglevel=INFO
```

---

## 3. TÁI CẤU TRÚC CODE BACKEND & TÍCH HỢP REST API

### 3.1 Cấu trúc thư mục Backend sau khi gộp

```
personalized-learning-system/backend/app/
├── api/
│   └── v1/
│       ├── router.py
│       └── routes/
│           ├── exam_workflow.py   <-- [NEW] API Route xử lý OCR & Parser Đề thi/Bảng điểm
│           └── ... (các route hiện có)
├── services/
│   ├── ocr_service.py             <-- [NEW] Chứa logic run_gemini_ocr từ WorkFlow/app.py
│   ├── exam_parser_service.py    <-- [NEW] Chứa logic từ WorkFlow/parser.py
│   ├── crawler_service.py        <-- [NEW] Chứa logic crawler từ WorkFlow/crawler_service.py
│   └── ...
```

### 3.2 Code Chi Tiết: `backend/app/services/exam_parser_service.py`

Chuyển đổi file `WorkFlow/parser.py` thành service module trong backend:

```python
import re
from typing import Dict, Any

def auto_format_math_latex(text: str) -> str:
    r"""
    Chuẩn hoá cú pháp LaTeX từ nhiều nguồn khác nhau.
    - \( ... \) -> $ ... $   (inline)
    - \[ ... \] -> $$ ... $$ (display)
    """
    if not text:
        return ""
    text = text.replace(r'\\(', '$').replace(r'\\)', '$')
    text = text.replace(r'\\\[', '$$').replace(r'\\\]', '$$')
    text = text.replace(r'\(', '$').replace(r'\)', '$')
    text = text.replace(r'\[', '$$').replace(r'\]', '$$')
    return text

def parse_exam_questions(text: str) -> Dict[str, Any]:
    """
    Parse Markdown/LaTeX text thành cấu trúc đề thi có phân cấp.
    """
    text_clean = auto_format_math_latex(text)

    lines = text_clean.split('\n')
    header_lines = []
    questions = []

    question_pattern = re.compile(
        r'^(Câu|Bài)\s+([IVXLCDM0-9]+)[:\.]?\s*(?:\(([^)]+)\))?',
        re.IGNORECASE
    )

    points_pattern = re.compile(
        r'\(?\s*([0-9]+[,\.][0-9]+\s*điểm|[0-9]+\s*đ(?:iểm)?)\s*\)?',
        re.IGNORECASE
    )

    current_q = None

    for line in lines:
        raw_stripped = line.strip()
        clean_line = re.sub(r'[#*_]', '', raw_stripped).strip()
        match = question_pattern.search(clean_line)

        if match:
            if current_q:
                current_q["content"] = current_q["content"].strip()
                questions.append(current_q)

            q_prefix = match.group(1).capitalize()
            q_num = match.group(2)
            q_title = f"{q_prefix} {q_num}"
            
            pts = None
            pts_match = points_pattern.search(raw_stripped)
            if pts_match:
                pts = pts_match.group(1)

            current_q = {
                "title": q_title,
                "points": pts,
                "content": raw_stripped,
                "raw_line": line
            }
        else:
            if current_q is not None:
                current_q["content"] += "\n" + line
            else:
                header_lines.append(line)

    if current_q:
        current_q["content"] = current_q["content"].strip()
        questions.append(current_q)

    return {
        "header": "\n".join(header_lines).strip(),
        "total_questions": len(questions),
        "questions": questions,
        "full_text": text_clean
    }
```

### 3.3 Code Chi Tiết: `backend/app/services/ocr_service.py`

Tích hợp gọi Gemini OCR bằng SDK `google-genai` chính thức:

```python
import os
import json
from typing import Dict, Any
from google import genai
from google.genai import types

_GEMINI_OCR_PROMPT = """Bạn là một mô hình phân tích và bóc tách tài liệu giáo dục.
Hãy phân tích hình ảnh/tài liệu để xác định xem đây là Đề thi (loại 1) hay Bảng điểm/Phiếu liên lạc (loại 2).
PHẢI TRẢ VỀ KẾT QUẢ DƯỚI DẠNG ĐỊNH DẠNG JSON.

Nếu là Đề thi (loai: 1), hãy trả về JSON theo cấu trúc sau:
{
  "loai": 1,
  "exam_content": "Trích xuất TOÀN BỘ nội dung đề thi thành Markdown kết hợp LaTeX. Giữ nguyên cấu trúc đề thi (Câu I, Bài 1...). Tất cả công thức toán học PHẢI bọc trong $...$ hoặc $$...$$. Đảm bảo cú pháp LaTeX chính xác."
}

Nếu là Bảng điểm / Phiếu liên lạc (loai: 2), hãy trả về JSON:
{
  "loai": 2,
  "metadata": {
    "grade": "Khối lớp (số) hoặc null",
    "semester": "Học kỳ (1 hoặc 2) hoặc null"
  },
  "columns": [
    { "key": "col_1", "label": "Chữ nguyên bản trên tiêu đề cột 1" }
  ],
  "rows": [
    {
      "subject": "Tên môn học hoặc Họ tên học sinh",
      "col_1": "Giá trị thô dạng chuỗi hoặc chuỗi rỗng"
    }
  ],
  "critic": "Lời nhận xét tổng quan cho toàn bộ bảng điểm"
}
"""

async def run_gemini_ocr(file_path: str, suffix: str) -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY chưa được cấu hình trong môi trường!")

    client = genai.Client(api_key=api_key)

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    mime_map = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".webp": "image/webp",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg"
    }
    mime = mime_map.get(suffix.lower(), "image/jpeg")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=mime),
            _GEMINI_OCR_PROMPT
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    try:
        return json.loads(response.text)
    except Exception:
        return {"loai": 1, "exam_content": response.text}
```

### 3.4 Code Chi Tiết: `backend/app/api/v1/routes/exam_workflow.py`

Tạo API endpoint chuẩn RESTful hỗ trợ upload file và bóc tách đề thi/bảng điểm:

```python
import os
import shutil
import tempfile
from typing import Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from pydantic import BaseModel

from app.services.ocr_service import run_gemini_ocr
from app.services.exam_parser_service import parse_exam_questions
from app.api.v1.auth import get_current_user  # Giữ nguyên cơ chế Auth của Personalized

router = APIRouter(prefix="/exam-workflow", tags=["Exam Workflow OCR"])

class ParseTextRequest(BaseModel):
    markdown_text: str

@router.post("/process-file")
async def process_file(
    file: UploadFile = File(...)
):
    suffix = os.path.splitext(file.filename)[1].lower()
    allowed_exts = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".docx", ".txt"}
    
    if suffix not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"Định dạng file {suffix} không được hỗ trợ!")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        ocr_result = await run_gemini_ocr(tmp_path, suffix)
        
        if ocr_result.get("loai") == 1:
            raw_text = ocr_result.get("exam_content", "")
            parsed_data = parse_exam_questions(raw_text)
            return {
                "status": "success",
                "type": "exam",
                "data": parsed_data
            }
        else:
            return {
                "status": "success",
                "type": "gradebook",
                "data": ocr_result
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý OCR: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@router.post("/parse-markdown")
async def parse_markdown(payload: ParseTextRequest):
    result = parse_exam_questions(payload.markdown_text)
    return {"status": "success", "data": result}
```

### 3.5 Đăng ký Route trong `backend/app/api/v1/router.py`

```python
from fastapi import APIRouter
from app.api.v1.routes import (
    catalog,
    content,
    exam_workflow,  # <-- Thêm route mới
    ...
)

api_router = APIRouter()
...
api_router.include_router(exam_workflow.router)  # <-- Nhúng router vào hệ thống
```

---

## 4. TÁI CẤU TRÚC FRONTEND VÀ ĐỒNG BỘ GIAO DIỆN (REACT + TAILWIND V4)

### 4.1 Chuyển đổi từ HTML Jinja2 sang React Component

Giao diện đơn thuần từ `templates/index.html` của WorkFlow sẽ được nâng cấp thành trang React chuyên nghiệp trong Personalized: `frontend/src/pages/ExamWorkflowPage.tsx`.

#### Thiết kế Giao diện Đồng bộ:
- **Card Container**: Bo tròn `rounded-2xl`, hiệu ứng shadow mượt, hỗ trợ Dark Mode (`bg-slate-900`, `text-slate-100`).
- **File Upload Zone**: Drag-and-drop mượt mà với icon `UploadCloud` từ Lucide-react.
- **Tabs Switcher**: Chuyển đổi linh hoạt giữa "Xem Đề thi gốc (Markdown)", "Các câu hỏi đã phân tách (LaTeX)", "Bảng điểm / Phiếu liên lạc".
- **Math Renderer**: Sử dụng KaTeX rendering công thức toán học $...$ inline và $$...$$ block.

### 4.2 Code Chi Tiết: `frontend/src/pages/ExamWorkflowPage.tsx`

```tsx
import React, { useState } from "react";
import { Upload, FileText, CheckCircle2, AlertCircle, Loader2, BookOpen } from "lucide-react";
import axios from "axios";

interface Question {
  title: string;
  points: string | null;
  content: string;
}

interface ExamParsedData {
  header: string;
  total_questions: number;
  questions: Question[];
  full_text: string;
}

export const ExamWorkflowPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExamParsedData | null>(null);
  const [activeTab, setActiveTab] = useState<"questions" | "raw">("questions");

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post("/api/v1/exam-workflow/process-file", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      if (response.data.type === "exam") {
        setResult(response.data.data);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Đã xảy ra lỗi trong quá trình xử lý file!");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header Page */}
      <div className="flex items-center space-x-3 border-b border-slate-700 pb-4">
        <BookOpen className="w-8 h-8 text-indigo-500" />
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Bóc Tách & OCR Đề Thi Math LaTeX</h1>
          <p className="text-sm text-slate-400">Trích xuất tự động câu hỏi, công thức toán học từ PDF/Ảnh bằng Gemini AI</p>
        </div>
      </div>

      {/* Upload Box */}
      <div className="bg-slate-800/60 rounded-xl p-6 border border-slate-700/60 shadow-lg">
        <form onSubmit={handleFileUpload} className="space-y-4">
          <div className="border-2 border-dashed border-slate-600 hover:border-indigo-500 rounded-lg p-8 text-center transition-colors">
            <input
              type="file"
              id="file-input"
              className="hidden"
              accept=".pdf,.png,.jpg,.jpeg,.webp,.docx"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            <label htmlFor="file-input" className="cursor-pointer flex flex-col items-center space-y-2">
              <Upload className="w-10 h-10 text-indigo-400" />
              <span className="text-slate-200 font-medium">
                {file ? file.name : "Kéo thả hoặc click để tải lên đề thi (PDF, DOCX, Ảnh)"}
              </span>
              <span className="text-xs text-slate-400">Hỗ trợ các định dạng: PDF, PNG, JPG, DOCX</span>
            </label>
          </div>

          <button
            type="submit"
            disabled={!file || loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-lg transition flex items-center justify-center space-x-2 disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <FileText className="w-5 h-5" />}
            <span>{loading ? "Đang xử lý OCR & Parser..." : "Bắt đầu Bóc Tách Đề Thi"}</span>
          </button>
        </form>

        {error && (
          <div className="mt-4 p-3 bg-red-900/40 border border-red-500/50 rounded-lg text-red-200 text-sm flex items-center space-x-2">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Render Results */}
      {result && (
        <div className="bg-slate-800/60 rounded-xl p-6 border border-slate-700/60 shadow-lg space-y-4">
          {/* Tab Navigation */}
          <div className="flex space-x-4 border-b border-slate-700 pb-2">
            <button
              onClick={() => setActiveTab("questions")}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition ${
                activeTab === "questions" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Danh Sách Câu Hỏi ({result.total_questions})
            </button>
            <button
              onClick={() => setActiveTab("raw")}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition ${
                activeTab === "raw" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Văn Bản Markdown / LaTeX Gốc
            </button>
          </div>

          {activeTab === "questions" ? (
            <div className="space-y-4">
              {result.questions.map((q, idx) => (
                <div key={idx} className="p-4 bg-slate-900/80 rounded-lg border border-slate-700/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-indigo-400">{q.title}</span>
                    {q.points && <span className="text-xs px-2 py-1 bg-indigo-950 text-indigo-300 rounded border border-indigo-800">{q.points}</span>}
                  </div>
                  <pre className="text-sm text-slate-200 whitespace-pre-wrap font-sans bg-slate-950/50 p-3 rounded">{q.content}</pre>
                </div>
              ))}
            </div>
          ) : (
            <pre className="text-sm text-slate-200 whitespace-pre-wrap bg-slate-950 p-4 rounded-lg font-mono overflow-x-auto">
              {result.full_text}
            </pre>
          )}
        </div>
      )}
    </div>
  );
};
```

### 4.3 Đăng ký Route Frontend trong `frontend/src/App.tsx`

Thêm đường dẫn mới cho Giáo viên / Admin sử dụng tính năng bóc tách đề thi WorkFlow:

```tsx
import { ExamWorkflowPage } from "./pages/ExamWorkflowPage";

// Trích đoạn trong App.tsx:
<Route element={<RequireRole allowed={["teacher", "admin"]} />}>
  <Route path="courses" element={<CourseManagementPage />} />
  <Route path="exam-workflow" element={<ExamWorkflowPage />} />  {/* <-- Route mới */}
</Route>
```

---

## 5. QUY TRÌNH KÍCH HOẠT DOCKER VÀ KIỂM THỬ KHÔNG LỖI (ZERO-ERROR BUILD)

Để đảm bảo hệ thống container chạy mượt mà 100% không phát sinh lỗi thư viện hay thiếu dependencies, thực hiện đúng quy trình sau:

### 5.1 Bước 1: Dọn dẹp cache cũ và Build lại Docker Images

Mở Terminal tại thư mục `personalized-learning-system`:

```bash
# 1. Stop toàn bộ container cũ
docker compose down -v

# 2. Build lại toàn bộ image không sử dụng cache cũ
docker compose build --no-cache

# 3. Khởi chạy hệ thống ở chế độ background
docker compose up -d
```

### 5.2 Bước 2: Kiểm tra Log Container Backend & Worker

Đảm bảo tất cả thư viện Python (`google-genai`, `beautifulsoup4`, `python-docx`, `openai`) đã được cài đặt thành công mà không gặp xung đột phiên bản:

```bash
# Kiểm tra log backend
docker compose logs -f backend

# Kiểm tra log worker
docker compose logs -f worker
```

**Dấu hiệu thành công trong Log:**
- `Application startup complete.`
- `Uvicorn running on http://0.0.0.0:8000`
- Alembic database migration thành công.

### 5.3 Bước 3: Kiểm tra môi trường Celery & Redis (Task Async)

Nếu muốn đưa công việc OCR lên Celery Worker xử lý bất đồng bộ:
1. Đảm bảo Redis container trả về `PONG`.
2. Worker nhận được task registered: `app.worker.celery_app.process_ocr_task`.

### 5.4 Bước 4: Test Upload & OCR Đề Thi Thực Tế

1. Truy cập Frontend tại `http://localhost:5173/exam-workflow` (hoặc thông qua AppShell navigation).
2. Upload 1 file ảnh đề thi Toán hoặc file PDF đề thi.
3. Kiểm tra kết quả bóc tách câu hỏi, tiêu đề bài thi và hiển thị công thức toán học $...$.

---

## 6. MA TRẬN KIỂM TRA LỖI THƯỜNG GẶP (TROUBLESHOOTING MATRIX)

| Mã Lỗi / Hiện Tượng | Nguyên Nhân | Cách Khắc Phục Chuẩn |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'google.genai'` | Chưa thêm `google-genai` vào `backend/requirements.txt` hoặc chưa re-build image | Thêm `google-genai>=1.0.0` vào `requirements.txt` và chạy `docker compose build backend` |
| `ValueError: GEMINI_API_KEY chưa được cấu hình` | Chưa khai báo API Key trong `.env` hoặc `docker-compose.yml` chưa load `env_file` | Kiểm tra file `.env`, gán `GEMINI_API_KEY=...` và restart container |
| `pdf2image.exceptions.PDFInfoNotInstalledError` | Thiếu package OS `poppler-utils` trong Dockerfile | Bổ sung `poppler-utils` vào lệnh `apt-get install` trong `backend/Dockerfile` |
| `ImportError: cannot import name 'genai' from 'google'` | Xung đột giữa package cũ `google-generativeai` và package mới `google-genai` | Xóa `google-generativeai` khỏi requirements, chỉ giữ duy nhất `google-genai>=1.0.0` |
| UI bị lệch layout, công thức LaTeX hiển thị chữ thô `$x^2$` | Chưa load CSS của KaTeX trong Frontend | Import CSS KaTeX `import 'katex/dist/katex.min.css';` vào `main.tsx` hoặc `index.css` |

---
*Tài liệu MERGE.md được tổng hợp chuẩn hóa cho việc tích hợp WorkFlow vào Personalized Learning System.*
