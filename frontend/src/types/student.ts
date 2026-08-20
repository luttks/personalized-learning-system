export interface StudentProfilePayload {
  education_level: "under_university" | "university";
  grade_level: number | null;
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
