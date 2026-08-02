export interface LearningGoal {
  type?: string | null;
  description?: string | null;
  target?: string | number | null;
}

export interface LearningPreferences {
  preferred_sequence: string[];
  content_formats: string[];
  preferred_difficulty?: string | null;
}

export interface LearnerProfilePayload {
  education_level?: string | null;
  subject?: string | null;
  learning_goal?: LearningGoal | null;
  deadline?: string | null;
  current_level?: string | null;
  known_concepts?: string[] | null;
  weak_concepts?: string[] | null;
  misconceptions?: string[] | null;
  minutes_per_day?: number | null;
  days_per_week?: number | null;
  available_periods?: string[] | null;
  learning_preferences?: LearningPreferences | null;
  confidence_scores?: Record<string, number>;
}

export interface LearnerProfile {
  id: string;
  user_id: string;
  education_level: string | null;
  subject: string | null;
  learning_goal: LearningGoal;
  deadline: string | null;
  current_level: string | null;
  known_concepts: string[];
  weak_concepts: string[];
  misconceptions: string[];
  minutes_per_day: number | null;
  days_per_week: number | null;
  available_periods: string[];
  learning_preferences: LearningPreferences;
  diagnostic_results: Array<Record<string, unknown>>;
  confidence_scores: Record<string, number>;
  missing_fields: string[];
  profile_version: number;
  created_at: string;
  updated_at: string;
}

export interface UnderstandingResponse {
  profile_patch: LearnerProfilePayload;
  evidence: Array<Record<string, unknown>>;
  missing_fields: string[];
  contradictions: Array<Record<string, unknown>>;
  clarification_question: string | null;
  diagnostic_required: boolean;
  profile: LearnerProfile;
}

export interface LearningEventPayload {
  topic_id: string;
  correct: boolean;
  difficulty: number;
  hint_used: boolean;
  attempt_count: number;
  source: string;
}

export interface Mastery {
  topic_id: string;
  mastery_score: number;
  confidence: number;
  repeated_errors: number;
  level: string;
  last_assessed_at: string | null;
}

export interface ConceptInput {
  id: string;
  name: string;
  description?: string | null;
  difficulty: number;
  estimated_minutes: number;
  prerequisites: string[];
}

export interface RoadmapPayload {
  title?: string | null;
  target_concept_ids: string[];
  concepts: ConceptInput[];
  required_mastery: number;
  start_date: string;
}

export interface RoadmapItem {
  concept_id: string;
  title: string;
  sequence: number;
  session_number: number;
  planned_date: string;
  estimated_minutes: number;
  activity_type: string;
}

export interface Roadmap {
  id: string;
  status: string;
  title: string;
  subject: string;
  deadline: string | null;
  total_estimated_minutes: number;
  profile_version: number;
  learning_gaps: Array<Record<string, unknown>>;
  skipped_concepts: Array<Record<string, unknown>>;
  items: RoadmapItem[];
}
