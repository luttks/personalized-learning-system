# HƯỚNG DẪN KHỞI CHẠY HỆ THỐNG DỰ ÁN (RUN.MD)

Tài liệu này hướng dẫn chi tiết từng bước để **Clone mã nguồn từ GitHub** và **Khởi chạy hệ thống hoàn chỉnh bằng Docker Compose** cho dự án **Personalized Learning System** (đã gộp đầy đủ các tính năng bóc tách đề thi, OCR Gemini, LaTeX parser và parallel crawler từ dự án WorkFlow).

---

## 1. YÊU CẦU MÔI TRƯỜNG (PREREQUISITES)

Trước khi bắt đầu, đảm bảo máy tính của bạn đã cài đặt các công cụ sau:

- **Git**: [Tải về tại git-scm.com](https://git-scm.com/)
- **Docker Desktop** (hoặc **Docker Engine + Docker Compose** trên Linux): [Tải về tại docker.com](https://www.docker.com/)
- **Cấu hình tối thiểu đề xuất**:
  - RAM: $\ge$ 8 GB (dành cho các container Docker)
  - CPU: $\ge$ 4 Cores
  - Dung lượng ổ cứng: $\ge$ 10 GB trống

---

## 2. QUY TRÌNH TỪNG BƯỚC KHỞI CHẠY (STEP-BY-STEP GUIDE)

### Bước 1: Clone dự án từ GitHub

Mở Terminal / PowerShell / Command Prompt và chạy lệnh clone repository về máy:

```bash
# Clone source code từ GitHub
git clone <repository_url_cua_ban>

# Di chuyển vào thư mục dự án
cd personalized-learning-system
```

---

### Bước 2: Thiết lập tệp cấu hình môi trường `.env`

Tạo tệp cấu hình `.env` từ tệp mẫu `.env.example`:

**Trên Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**Trên Linux / macOS / Git Bash:**
```bash
cp .env.example .env
```

> [!IMPORTANT]
> Mở tệp `.env` vừa tạo và cập nhật các thông số quan trọng:
> 1. `POSTGRES_PASSWORD`: Điền mật khẩu cho cơ sở dữ liệu PostgreSQL (ví dụ: `secretpassword123`).
> 2. `JWT_SECRET_KEY`: Điền một chuỗi bảo mật ngẫu nhiên (ví dụ: `supersecretjwtkey987654321`).
> 3. `GEMINI_API_KEY`: Điền API Key Gemini của bạn để sử dụng tính năng OCR Đề thi/Bảng điểm bằng Gemini AI và Gợi ý bài học.

---

### Bước 3: Khởi chạy toàn bộ hệ thống bằng Docker Compose

Chạy câu lệnh sau để Docker tự động build hình ảnh (image) và khởi chạy tất cả 5 container:

```bash
docker compose up -d --build
```

#### Các container sẽ được tạo và vận hành:
1. **`learning-postgres`**: Cơ sở dữ liệu PostgreSQL 17 tích hợp tiện ích mở rộng vector `pgvector`.
2. **`learning-redis`**: Bộ nhớ đệm Redis 7 làm Celery Broker & Result Store.
3. **`learning-backend`**: Máy chủ FastAPI Backend (Async, Python 3.13, tự động chạy Alembic DB migration).
4. **`learning-worker`**: Celery Worker xử lý tác vụ ngầm (OCR Tesseract, Poppler PDF, Document analysis).
5. **`learning-frontend`**: Giao diện người dùng SPA (React 19, Vite, Tailwind CSS v4).

---

### Bước 4: Kiểm tra trạng thái và log hệ thống

Kiểm tra danh sách các container đang chạy:

```bash
docker compose ps
```

*Tất cả 5 container phải ở trạng thái **`Up`** hoặc **`Up (healthy)`**.*

Xem log hệ thống để đảm bảo không phát sinh lỗi:

```bash
# Xem log của tất cả các service
docker compose logs -f

# Hoặc xem log riêng của backend
docker compose logs -f backend
```

---

### Bước 5: Truy cập các cổng dịch vụ (Endpoints)

Sau khi hệ thống khởi chạy thành công, truy cập các địa chỉ sau trên trình duyệt:

- 🌐 **Giao diện chính (Frontend App)**: `http://localhost:5173`
- 🎯 **Chức năng Bóc tách đề thi (Exam Workflow)**: `http://localhost:5173/exam-workflow`
- 📚 **Tài liệu API Backend (Swagger UI)**: `http://localhost:8000/docs`
- 💚 **Kiểm tra sức khỏe API Backend (Health Check)**: `http://localhost:8000/api/v1/health`

---

## 3. KIỂM THỬ HỆ THỐNG TỰ ĐỘNG (AUTOMATED TESTING)

Bạn có thể chạy toàn bộ bộ kiểm thử tự động ngay bên trong môi trường Docker:

### Kiểm thử Backend (Pytest Suite)
```bash
docker compose exec backend pytest
```
*Tất cả 42/42 unit tests (bao gồm OCR, Exam Workflow, RAG, Catalog, Security...) sẽ chạy và thông báo kết quả passed.*

### Kiểm thử Biên dịch Frontend (TypeScript Check)
```bash
docker compose exec frontend npm run build
```
*Kiểm tra biên dịch static bundle React/Vite đảm bảo không có lỗi cú pháp.*

---

## 4. HƯỚNG DẪN TẮT ỨNG DỤNG & CÁC LỆNH VẬN HÀNH (STOPPING & OPERATING COMMANDS)

### 🔴 4.1 Các cách Tắt Ứng dụng (Shutdown Options)

Tùy vào nhu cầu sử dụng, bạn chọn 1 trong các cách tắt ứng dụng sau:

#### Cách 1: Tạm dừng ứng dụng (Giữ nguyên container & dữ liệu)
Sử dụng khi bạn muốn tạm dừng để giải phóng tài nguyên CPU/RAM, sau này bật lại nhanh:
```bash
# Tắt tạm thời các container
docker compose stop

# Để bật lại sau đó mà không cần build lại:
docker compose start
```

#### Cách 2: Tắt và gỡ bỏ container (An toàn, dữ liệu Database vẫn còn nguyên)
Sử dụng khi bạn muốn tắt sạch sẽ ứng dụng. Lần sau chỉ cần `docker compose up -d` là chạy lại:
```bash
docker compose down
```

#### Cách 3: Tắt và XÓA HOÀN TOÀN dữ liệu Database (Clean Reset)
CẢNH BÁO: Lệnh này sẽ xóa toàn bộ cơ sở dữ liệu và khôi phục về trạng thái ban đầu:
```bash
docker compose down -v
```

---

### 🟢 4.2 Cách Khởi chạy lại Ứng dụng (Run Again after Shutdown)

Sau khi bạn đã tắt ứng dụng bằng lệnh `docker compose down` hoặc `docker compose stop`, để chạy lại ứng dụng:

#### Trường hợp 1: Khởi chạy lại thông thường (Nhanh nhất)
Sử dụng khi bạn muốn bật lại ứng dụng mà không thay đổi mã nguồn:
```bash
docker compose up -d
```

#### Trường hợp 2: Khởi chạy lại và Build lại mã nguồn mới
Sử dụng khi bạn vừa cập nhật mã nguồn mới hoặc cài đặt thêm các thư viện trong `requirements.txt` / `package.json`:
```bash
docker compose up -d --build
```

---

### 🔄 4.3 Tải lại / Rebuild từng Dịch vụ cụ thể

Nếu bạn thay đổi mã nguồn Backend hoặc Frontend mà muốn cập nhật lại ngay:

```bash
# Rebuild lại Backend
docker compose up -d --build backend

# Restart lại Frontend
docker compose restart frontend
```

---

### 📋 4.4 Cách Xem Log Hệ thống (Viewing Logs)

Khi ứng dụng chạy ngầm (`-d`), bạn có thể xem log theo các câu lệnh sau:

#### Xem log của TOÀN BỘ các service liên tục (Live Stream):
```bash
docker compose logs -f
```
*(Bấm **`Ctrl` + `C`** để dừng xem log).*

#### Xem log của từng Service cụ thể:
```bash
# Xem log Backend (FastAPI / Uvicorn)
docker compose logs -f backend

# Xem log Worker Celery (OCR, Tasks)
docker compose logs -f worker

# Xem log Frontend (React / Vite)
docker compose logs -f frontend

# Xem log Database (PostgreSQL)
docker compose logs -f postgres
```

#### Xem 100 dòng log gần nhất:
```bash
docker compose logs --tail=100 -f backend
```

---

## 5. XỬ LÝ SỰ CỐ THƯỜNG GẶP (TROUBLESHOOTING)

> [!TIP]
> **Lỗi `ModuleNotFoundError: No module named 'bs4'` hoặc thiếu thư viện Python**:
> - Chạy lệnh rebuild lại image backend: `docker compose build backend worker` rồi `docker compose up -d`.

> [!TIP]
> **Trình duyệt hiển thị trang cũ / không thấy thay đổi mới**:
> - Nhấn **`Ctrl` + `F5`** (hoặc **`Ctrl` + `Shift` + `R`**) trên trình duyệt để xóa cache trang web.

> [!TIP]
> **Lỗi thiếu GEMINI_API_KEY khi Bóc tách đề thi**:
> - Đảm bảo bạn đã điền `GEMINI_API_KEY=your_actual_key` trong file `.env` rồi khởi động lại backend: `docker compose restart backend`.

---

## 6. HƯỚNG DẪN KẾT NỐI DATABASE BẰNG PGADMIN 4

Dưới đây là hướng dẫn chi tiết để bạn kết nối ứng dụng **pgAdmin 4** (hoặc DBeaver / TablePlus) từ máy tính vào cơ sở dữ liệu PostgreSQL đang chạy trong Docker:

### Các bước thực hiện:

1. **Mở pgAdmin 4** trên máy tính.
2. Tại cây bên trái, nhấp chuột phải vào **Servers** ➔ Chọn **Register** ➔ **Server...**
3. Điền thông tin kết nối:
   - **Tab `General`**:
     - `Name`: `Personalized Learning Docker` (hoặc tên tùy chọn)
   - **Tab `Connection`**:
     - `Host name/address`: `localhost` *(hoặc `127.0.0.1`)*
     - `Port`: `5433` *(Cổng mapped của Docker để tránh đụng độ với Postgres cài sẵn trên Windows)*
     - `Maintenance database`: `personalized_learning`
     - `Username`: `learning_user`
     - `Password`: `learning_password_secure123`
     - Tích chọn **Save password?** (Lưu mật khẩu).
4. Bấm **Save** để kết nối.

### Xem dữ liệu các Bảng (Tables):
- Mở rộng: **Servers** ➔ **Personalized Learning Docker** ➔ **Databases** ➔ **`personalized_learning`** ➔ **Schemas** ➔ **`public`** ➔ **`Tables`**.
- Nhấp chuột phải vào bảng (ví dụ `users`, `student_profiles`, `courses`, `document_analyses`) ➔ chọn **View/Edit Data** ➔ **All Rows** để xem toàn bộ dữ liệu.

