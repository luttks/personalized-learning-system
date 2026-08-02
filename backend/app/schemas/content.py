from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CourseCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    subject: str = Field(min_length=1, max_length=150)
    grade_level: int = Field(ge=1, le=12)
    description: str | None = Field(default=None, max_length=5000)


class CourseResponse(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    subject: str
    grade_level: int
    description: str | None
    status: str
    published_version_id: UUID | None
    active_publication_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseVersionResponse(BaseModel):
    id: UUID
    course_id: UUID
    version_number: int
    status: str
    created_by_id: UUID
    failure_code: str | None
    failure_detail: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: UUID
    course_version_id: UUID
    original_name: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentJobResponse(BaseModel):
    id: UUID
    document_id: UUID
    course_version_id: UUID
    course_id: UUID
    version_number: int
    original_name: str
    version_status: str
    status: str
    progress: int
    current_step: str | None
    retry_count: int
    error_code: str | None
    error_detail: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    course_version: CourseVersionResponse
    document: DocumentResponse
    job: DocumentJobResponse


class CourseDocumentItem(BaseModel):
    document: DocumentResponse
    version: CourseVersionResponse
    job: DocumentJobResponse
    analysis_status: str | None
    source_characters: int


class AnalysisChapter(BaseModel):
    number: int
    title: str
    summary: str
    key_points: list[str] = Field(default_factory=list)


class DocumentStructure(BaseModel):
    title: str
    summary: str
    chapters: list[AnalysisChapter] = Field(default_factory=list)
    source: str = "fallback"


class DocumentPreviewResponse(BaseModel):
    document: DocumentResponse
    version: CourseVersionResponse
    status: str
    original_text: str
    llm_input_text: str
    edited_text: str | None
    effective_text: str
    edited_by_id: UUID | None
    edited_at: datetime | None
    source_characters: int
    structure: DocumentStructure | None = None


class DocumentEditRequest(BaseModel):
    edited_text: str = Field(min_length=1, max_length=200_000)


class DocumentAnalysisResponse(BaseModel):
    id: UUID
    course_version_id: UUID
    document_id: UUID
    status: str
    source_characters: int
    structure: DocumentStructure
    original_structure: DocumentStructure
    edited_structure: DocumentStructure | None
    structure_edited_by_id: UUID | None
    structure_edited_at: datetime | None
    provider: str | None
    model: str | None
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    updated_at: datetime


class DocumentAnalysisEditRequest(BaseModel):
    structure: DocumentStructure


class RagIndexResponse(BaseModel):
    course_version_id: UUID
    chunk_count: int
    embedding_model: str


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=5, ge=1, le=20)


class RagSearchResult(BaseModel):
    chunk_id: UUID
    chunk_index: int
    text: str
    page_number: int | None
    source_label: str
    cosine_score: float
    score: float


class RagSearchResponse(BaseModel):
    course_version_id: UUID
    query: str
    index_count: int
    results: list[RagSearchResult]


class CatalogConceptResponse(BaseModel):
    id: UUID
    stable_key: str
    order_index: int
    title: str
    description: str
    estimated_minutes: int
    prerequisite_keys: list[str]


class CatalogLessonResponse(BaseModel):
    id: UUID
    order_index: int
    title: str
    summary: str
    source_label: str
    chunk_count: int
    concepts: list[CatalogConceptResponse]


class CatalogChapterResponse(BaseModel):
    id: UUID
    order_index: int
    title: str
    summary: str
    source_label: str
    lessons: list[CatalogLessonResponse]


class CourseCatalogResponse(BaseModel):
    course_version_id: UUID
    ready: bool
    issues: list[str]
    chapter_count: int
    lesson_count: int
    concept_count: int
    chunk_count: int
    chapters: list[CatalogChapterResponse]


class CatalogConceptEdit(BaseModel):
    id: UUID
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=10_000)
    estimated_minutes: int = Field(ge=5, le=480)


class CatalogLessonEdit(BaseModel):
    id: UUID
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=20_000)
    concepts: list[CatalogConceptEdit] = Field(min_length=1)


class CatalogChapterEdit(BaseModel):
    id: UUID
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=20_000)
    lessons: list[CatalogLessonEdit] = Field(min_length=1)


class CourseCatalogEditRequest(BaseModel):
    chapters: list[CatalogChapterEdit] = Field(min_length=1)


class CourseQualityVersionResponse(BaseModel):
    course_version_id: UUID
    version_number: int
    document_id: UUID
    original_name: str
    processing_status: str
    ready: bool
    issues: list[str]
    chapter_count: int
    lesson_count: int
    concept_count: int
    chunk_count: int


class CourseQualityGateResponse(BaseModel):
    course_id: UUID
    ready: bool
    issues: list[str]
    document_count: int
    ready_document_count: int
    chapter_count: int
    lesson_count: int
    concept_count: int
    chunk_count: int
    versions: list[CourseQualityVersionResponse]


class CoursePublicationResponse(BaseModel):
    id: UUID
    course_id: UUID
    revision: int
    status: str
    version_ids: list[UUID]
    quality_snapshot: dict
    published_by_id: UUID
    published_at: datetime
    unpublished_at: datetime | None


class PublishedCourseSummary(BaseModel):
    id: UUID
    title: str
    subject: str
    grade_level: int
    description: str | None
    publication_revision: int
    document_count: int
    chapter_count: int
    lesson_count: int
    concept_count: int
    published_at: datetime


class PublishedCourseVersion(BaseModel):
    course_version_id: UUID
    version_number: int
    original_name: str
    chapter_count: int
    lesson_count: int
    concept_count: int
    chunk_count: int
    chapters: list[CatalogChapterResponse]


class PublishedCourseDetail(PublishedCourseSummary):
    publication_id: UUID
    versions: list[PublishedCourseVersion]


class LearnerCourseProfileUpsert(BaseModel):
    learning_goal: str = Field(min_length=10, max_length=5000)
    start_date: date
    deadline: date
    minutes_per_day: int = Field(ge=10, le=600)
    days_per_week: int = Field(ge=1, le=7)
    available_periods: list[str] = Field(min_length=1, max_length=14)
    content_formats: list[str] = Field(min_length=1, max_length=8)

    @classmethod
    def _clean_choices(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    def model_post_init(self, _context: object) -> None:
        self.available_periods = self._clean_choices(self.available_periods)
        self.content_formats = self._clean_choices(self.content_formats)
        if not self.available_periods or not self.content_formats:
            raise ValueError("Cần chọn ít nhất một khung giờ và định dạng học.")
        if self.deadline < self.start_date:
            raise ValueError("Deadline không được trước ngày bắt đầu.")


class LearnerCourseProfileResponse(LearnerCourseProfileUpsert):
    id: UUID
    user_id: UUID
    course_id: UUID
    publication_id: UUID
    version_ids: list[UUID]
    profile_version: int
    stale: bool
    created_at: datetime
    updated_at: datetime
