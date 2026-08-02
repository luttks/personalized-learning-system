# Kế hoạch triển khai theo cổng nghiệm thu

Tài liệu nguồn: [personalized-learning-workflow-spec.md](./personalized-learning-workflow-spec.md)

Nguyên tắc thực hiện: mỗi giai đoạn phải hoàn thành code và automated test, sau đó dừng để người dùng kiểm tra thủ công. Chỉ chuyển giai đoạn khi người dùng xác nhận.

## Giai đoạn 1 - Nền tảng khóa học và tài liệu

Trạng thái: **Hoàn thành code và automated test - chờ người dùng nghiệm thu**

1. Tạo schema `courses`, `course_versions`, `documents`, `document_jobs`.
2. Tạo API tạo/list khóa học cho Admin/Giảng viên theo ownership.
3. Tạo local file storage adapter và upload validator.
4. Tạo API upload trả `202` cùng `job_id`.
5. Tạo Celery task khung xác minh file lưu trữ và cập nhật tiến độ job.
6. Tạo API xem trạng thái job có kiểm tra quyền.
7. Tạo màn hình quản lý khóa học, upload và theo dõi job.
8. Chạy migration/static checks/unit/API tests và bàn giao URL để nghiệm thu.
9. Danh sách tài liệu và toàn bộ phiên bản đã lưu theo từng khóa học: **đã hoàn thành**.
10. Preview văn bản OCR/parser đã lưu, có kiểm tra ownership: **đã hoàn thành**.
11. OCR PDF scan theo bố cục, tiếng Việt + tiếng Anh và retry không cần upload lại: **đã hoàn thành**.
12. Lưu riêng nội dung gốc, nội dung gửi LLM và bản người dùng chỉnh sửa: **đã hoàn thành**.
13. Editor nội dung tài liệu với audit người sửa/thời điểm sửa: **đã hoàn thành**.
14. Admin xóa vĩnh viễn tài liệu/version hoặc khóa học rác, kèm guard publish/processing và dọn file storage: **đã hoàn thành**.

Điều kiện qua cổng:

- Teacher chỉ thấy/quản lý khóa học do mình tạo; Admin thấy toàn bộ.
- File sai loại, sai signature hoặc quá dung lượng bị từ chối.
- File hợp lệ tạo đúng một course version, document và job.
- Worker xác minh checksum/kích thước và kết thúc ở `READY_FOR_ANALYSIS`; lỗi kết thúc ở `FAILED`.
- UI hiển thị course, version, job progress và lỗi có thể hành động.

## Giai đoạn 2 - Phân tích tài liệu và RAG

Trạng thái: **Demo đọc tài liệu và preview bằng LLM đã hoàn thành - chờ người dùng nghiệm thu**

1. Parser adapter cho PDF, DOCX, PPTX, TXT và OCR ảnh/PDF scan: **đã hoàn thành bản nền tảng**.
2. Preview LLM gồm tiêu đề, tóm tắt, chương và ý chính: **đã hoàn thành**.
3. Chuẩn hóa text và source span theo trang/vị trí: **đã có page/đoạn reference ở mức chunk; source span chi tiết chờ**.
4. Bóc lesson, concept và prerequisite: **đã hoàn thành bản nền tảng idempotent, stable concept key, graph tuyến tính không cycle và liên kết chunk → lesson**.
5. Chunk, metadata, embedding và pgvector retrieval: **đã hoàn thành MVP feature-hash 384 chiều + hybrid search, filter theo course version và UI kiểm tra RAG**.
6. Quality gate, review UI và publish course version: **đã hoàn thành publication snapshot theo revision, Publish/Unpublish và khóa chỉnh sửa Version đang publish**.
   - Quality gate cuối chạy ở cấp khóa học, gom mọi tài liệu/version theo thứ tự, nối prerequisite xuyên version và chặn nếu bất kỳ tài liệu nào chưa đạt: **đã hoàn thành**.
   - Admin xem chi tiết và chỉnh sửa/lưu Chapter, Lesson, Concept, mô tả và thời lượng; aggregate build bảo toàn catalog đã duyệt: **đã hoàn thành**.
7. Test idempotency, citation, graph cycle, partial failure và publish guard: chờ.

## Giai đoạn 3 - Catalog và onboarding

Trạng thái: **Chờ**

1. Catalog/preview chỉ đọc publication snapshot đang hoạt động: **đã hoàn thành API và giao diện học sinh**.
2. Learner-course profile và onboarding schema: **đã hoàn thành API và form theo từng khóa học**.
3. Validation mục tiêu, deadline, capacity và sở thích: **đã hoàn thành ở client, API và database**.
4. Profile versioning và stale detection: **đã hoàn thành theo publication snapshot**.

## Giai đoạn 4 - Diagnostic assessment

Trạng thái: **Đang phát triển - đã có assessment/attempt, chấm điểm idempotent và cập nhật mastery**.

Trạng thái: **Chờ**

1. Blueprint và question generation có source reference.
2. Assessment/question versioning.
3. Attempt, response, submit idempotency và deterministic scoring.
4. Mastery/evidence theo concept.

## Giai đoạn 5 - Lộ trình cá nhân hóa

Trạng thái: **Đang phát triển - đã có planner course-specific và proposal API/UI**

1. Nối course concept graph vào planner hiện có: **đã hoàn thành**.
2. Gap/prerequisite/capacity planning: **đã hoàn thành deterministic proposal**.
3. RAG context và LLM JSON contract.
4. Validator, retry giới hạn và deterministic fallback.
5. Proposal API/UI và source reference: **đã hoàn thành bản proposal đầu tiên**.

## Giai đoạn 6 - Revision, acceptance và progress

Trạng thái: **Chờ**

1. Immutable revision feedback và path versioning.
2. Optimistic concurrency và stale path policy.
3. Accept idempotency và progress transaction.
4. Màn hình buổi học đầu tiên.

## Giai đoạn 7 - Hardening và regression

Trạng thái: **Chờ**

1. Outbox/job recovery, rate limit và quota.
2. Security suite cho upload, prompt injection, RBAC và answer leakage.
3. Observability, metrics, retention và audit.
4. Performance/concurrency và end-to-end regression.
