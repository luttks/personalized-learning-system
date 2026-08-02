export type LearningMode = "visual" | "reading" | "practice" | "balanced";
export type ExplanationDepth = "short" | "medium" | "detailed";

export interface StudentProfilePayload {
  date_of_birth: string | null;
  grade_level: number;
  school_name: string | null;
  city: string | null;
  preferred_learning_mode: LearningMode;
  explanation_depth: ExplanationDepth;
  preferred_session_minutes: number;
  study_days_per_week: number;
  study_minutes_per_day: number;
  favourite_subjects: string | null;
  difficult_subjects: string | null;
  learning_notes: string | null;
}

export interface StudentProfile extends StudentProfilePayload {
  id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}
