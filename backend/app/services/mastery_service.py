from dataclasses import dataclass


def update_mastery(
    old_mastery: float,
    *,
    correct: bool,
    difficulty: float,
    hint_used: bool,
    attempt_count: int,
) -> float:
    performance = 1.0 if correct else 0.0
    if hint_used:
        performance *= 0.75
    if attempt_count > 1:
        performance *= max(0.5, 1 - 0.1 * (attempt_count - 1))

    weight = 0.15 + difficulty * 0.15
    updated = old_mastery * (1 - weight) + performance * weight
    return round(max(0.0, min(1.0, updated)), 4)


def mastery_level(score: float) -> str:
    if score < 0.3:
        return "unknown"
    if score < 0.5:
        return "developing"
    if score < 0.7:
        return "basic"
    if score < 0.85:
        return "proficient"
    return "mastered"


@dataclass(frozen=True)
class MasterySnapshot:
    score: float
    confidence: float = 0.0
    repeated_errors: int = 0
