export type LearningMode = "theory_first" | "practice_first" | "step_by_step" | "balanced";
export type ExplanationDepth = "short" | "medium" | "detailed";

export interface StudentProfilePayload {
  education_level: "under_university" | "university";
  grade_level: number | null;
  preferred_learning_mode: LearningMode;
  explanation_depth: ExplanationDepth;
  preferred_session_minutes: number;
  study_days_per_week: number;
  study_minutes_per_day: number;
}

export interface StudentProfile extends StudentProfilePayload {
  id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}
