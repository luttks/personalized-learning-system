# Personalized Learning System

Hệ thống xây dựng lộ trình học tập cá nhân hóa cho học sinh. Dự án gồm giao diện React, API FastAPI, PostgreSQL với pgvector, Redis và Celery worker để xử lý các tác vụ nền như phân tích tài liệu.

## Công nghệ chính

- Frontend: React 19, TypeScript, Vite và Tailwind CSS
- Backend: Python 3.13, FastAPI, SQLAlchemy và Alembic
- Database: PostgreSQL 17 với pgvector
- Queue: Redis và Celery
- Xử lý tài liệu: PyMuPDF, pypdf và Tesseract OCR (tiếng Việt + tiếng Anh)

## Chạy nhanh bằng Docker

Đây là cách được khuyến nghị vì Docker sẽ cài và kết nối toàn bộ dịch vụ cần thiết.

### 1. Yêu cầu

Cài sẵn:

- Git
- Docker Desktop (Windows/macOS) hoặc Docker Engine kèm Docker Compose v2 (Linux)
- Các cổng `5173`, `8000`, `5432` và `6379` đang trống

Kiểm tra Docker:

```bash
docker --version
docker compose version
```

Các ví dụ bên dưới dùng cú pháp `docker compose`. Nếu máy chỉ nhận lệnh `docker-compose`, hãy thay `docker compose` bằng `docker-compose` trong tất cả câu lệnh; chức năng tương đương nhau với Docker Compose v2.

### 2. Tải source code

```bash
git clone <repository-url>
cd personalized-learning-system
```

Thay `<repository-url>` bằng URL HTTPS hoặc SSH của repository.

### 3. Tạo file cấu hình môi trường

macOS, Linux hoặc Git Bash:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Mở `.env` và thay ít nhất hai giá trị sau:

```dotenv
POSTGRES_PASSWORD=your-strong-database-password
JWT_SECRET_KEY=your-random-secret-with-at-least-32-characters
```

Có thể tạo JWT secret trên macOS/Linux bằng lệnh:

```bash
openssl rand -hex 32
```

Các tính năng dùng mô hình ngôn ngữ cần cấu hình thêm:

```dotenv
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=<model-name>
LLM_API_KEY=<api-key>
```

Không commit file `.env` hoặc API key lên Git. Nếu chưa cấu hình LLM, phần còn lại của ứng dụng vẫn khởi động nhưng các tính năng phân tích đầu vào học sinh bằng AI sẽ không hoạt động.

### 4. Khởi động hệ thống

```bash
docker compose up --build
```

Lần chạy đầu có thể mất vài phút để tải image và cài dependency. Backend sẽ tự chạy toàn bộ database migration sau khi PostgreSQL sẵn sàng.

Muốn chạy dưới nền:

```bash
docker compose up --build -d
```

### 5. Truy cập ứng dụng

| Thành phần | Địa chỉ |
| --- | --- |
| Giao diện | http://localhost:5173 |
| API | http://localhost:8000 |
| Swagger API docs | http://localhost:8000/docs |
| API health | http://localhost:8000/api/v1/health |
| Database health | http://localhost:8000/api/v1/health/database |

Tại giao diện, chọn **Đăng ký** để tạo tài khoản học sinh đầu tiên.

### 6. Dừng hệ thống

```bash
docker compose down
```

Dữ liệu PostgreSQL, Redis và dependency frontend vẫn được giữ trong Docker volumes. Để xóa toàn bộ dữ liệu và tạo lại từ đầu:

```bash
docker compose down -v
```

Lưu ý: tùy chọn `-v` xóa database của môi trường local và không thể khôi phục nếu chưa sao lưu.

## Các lệnh Docker thường dùng

Xem trạng thái service:

```bash
docker compose ps
```

Theo dõi toàn bộ log:

```bash
docker compose logs -f
```

Theo dõi riêng backend hoặc worker:

```bash
docker compose logs -f backend
docker compose logs -f worker
```

Chạy migration thủ công:

```bash
docker compose exec backend alembic upgrade head
```

Sau khi pull source mới:

```bash
git pull
docker compose up --build -d
```

## Chạy development không đóng gói ứng dụng trong Docker

Cách này phù hợp khi cần debug frontend/backend trực tiếp trên máy. Các lệnh dưới đây dành cho macOS/Linux; trên Windows nên dùng WSL hoặc điều chỉnh lệnh kích hoạt virtual environment.

### Yêu cầu

- Python 3.13
- Node.js 24 và npm
- PostgreSQL 17 có extension pgvector
- Redis 7
- Tesseract OCR với language pack `eng` và `vie`

Có thể dùng Docker chỉ để chạy PostgreSQL và Redis:

```bash
cp .env.example .env
docker compose up -d postgres redis
```

### Backend

Tạo một bản cấu hình riêng cho backend:

```bash
cp .env backend/.env
```

Trong `backend/.env`, đổi hostname của các service từ Docker sang máy local:

```dotenv
DATABASE_URL=postgresql+asyncpg://learning_user:<password>@localhost:5432/personalized_learning
ALEMBIC_DATABASE_URL=postgresql+psycopg://learning_user:<password>@localhost:5432/personalized_learning
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

Giá trị `<password>` phải giống `POSTGRES_PASSWORD` trong file `.env` ở thư mục gốc.

Cài dependency, migrate database và chạy API:

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Mở terminal khác để chạy Celery worker:

```bash
cd backend
source .venv/bin/activate
celery -A app.worker.celery_app:celery_app worker --loglevel=INFO
```

### Frontend

Mở terminal khác:

```bash
cd frontend
npm ci
npm run dev
```

Frontend mặc định gọi API tại `http://localhost:8000/api/v1`. Khi cần đổi địa chỉ API, tạo `frontend/.env.local`:

```dotenv
VITE_API_URL=http://localhost:8000/api/v1
```

## Kiểm tra source code

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

Backend:

```bash
cd backend
source .venv/bin/activate
pytest -q
ruff check .
```

## Cấu trúc thư mục

```text
personalized-learning-system/
|-- backend/             FastAPI, Alembic, Celery và backend tests
|-- database/            Script khởi tạo extension PostgreSQL
|-- docs/                Tài liệu thiết kế và kế hoạch triển khai
|-- frontend/            React/Vite application
|-- uploads/             Tài liệu tải lên, không được commit
|-- .env.example         Mẫu biến môi trường
|-- docker-compose.yml   Cấu hình toàn bộ local stack
`-- README.md
```

## Xử lý lỗi thường gặp

### Port đã được sử dụng

Đổi `POSTGRES_PORT`, `BACKEND_PORT` hoặc `FRONTEND_PORT` trong `.env`. Nếu đổi frontend port, cập nhật thêm `CORS_ORIGINS` để khớp URL mới.

Redis hiện dùng trực tiếp cổng `6379` trong `docker-compose.yml`; hãy dừng Redis local đang chiếm cổng này trước khi chạy.

### Backend không kết nối được database

Kiểm tra container và log:

```bash
docker compose ps
docker compose logs postgres backend
```

Nếu vừa đổi `POSTGRES_DB`, `POSTGRES_USER` hoặc `POSTGRES_PASSWORD` sau khi database đã được tạo, Docker volume cũ vẫn giữ thông tin trước đó. Với môi trường local không cần giữ dữ liệu, chạy `docker compose down -v` rồi khởi động lại.

### OCR báo thiếu Tesseract hoặc language pack

Docker image backend đã cài sẵn Tesseract cho tiếng Anh và tiếng Việt. Nếu chạy backend trực tiếp trên máy, cần tự cài binary Tesseract và hai language pack `eng`, `vie`.

### Thay đổi dependency nhưng container vẫn dùng bản cũ

Build lại image:

```bash
docker compose build --no-cache backend frontend
docker compose up -d
```

## Lưu ý bảo mật

- Chỉ commit `.env.example`, tuyệt đối không commit `.env`.
- Dùng mật khẩu database và JWT secret khác nhau cho từng môi trường.
- Không dùng cấu hình Docker Compose hiện tại để public trực tiếp lên Internet; đây là cấu hình development có port database/Redis mở ra máy host và backend bật reload.
