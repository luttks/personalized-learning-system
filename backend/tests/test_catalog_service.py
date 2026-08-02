from app.services.catalog_service import stable_concept_key, vector_similarity


def test_stable_concept_key_handles_vietnamese_and_duplicates() -> None:
    first = stable_concept_key("Nghề nông trồng lúa nước", 1)
    repeated = stable_concept_key("Nghề nông trồng lúa nước", 2)

    assert first.startswith("001-nghe-nong-trong-lua-nuoc-")
    assert repeated.startswith("002-nghe-nong-trong-lua-nuoc-")
    assert first != repeated


def test_vector_similarity_uses_dot_product() -> None:
    assert vector_similarity([1.0, 0.0], [0.5, 0.5]) == 0.5
