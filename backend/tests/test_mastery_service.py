from app.services.mastery_service import mastery_level, update_mastery


def test_mastery_update_accounts_for_hint_and_attempts() -> None:
    direct = update_mastery(
        0.4, correct=True, difficulty=0.5, hint_used=False, attempt_count=1
    )
    assisted = update_mastery(
        0.4, correct=True, difficulty=0.5, hint_used=True, attempt_count=3
    )
    incorrect = update_mastery(
        0.4, correct=False, difficulty=0.5, hint_used=False, attempt_count=1
    )

    assert direct > assisted > incorrect
    assert 0 <= incorrect <= 1


def test_mastery_levels_cover_boundaries() -> None:
    assert mastery_level(0.29) == "unknown"
    assert mastery_level(0.30) == "developing"
    assert mastery_level(0.50) == "basic"
    assert mastery_level(0.70) == "proficient"
    assert mastery_level(0.85) == "mastered"
