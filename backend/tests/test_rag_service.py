from app.services.rag_service import feature_hash_embedding, split_content_chunks


def test_feature_hash_embedding_is_normalized_and_deterministic() -> None:
    first = feature_hash_embedding("Nghề nông trồng lúa nước")
    second = feature_hash_embedding("Nghề nông trồng lúa nước")

    assert first == second
    assert len(first) == 384
    assert abs(sum(value * value for value in first) - 1) < 0.000001


def test_split_content_chunks_preserves_page_reference() -> None:
    text = """[Trang 1]

Nội dung trang thứ nhất.

[Trang 2]

Nội dung trang thứ hai."""

    chunks = split_content_chunks(text, max_characters=30, overlap_characters=0)

    assert [chunk.page_number for chunk in chunks] == [1, 2]
    assert chunks[1].text == "Nội dung trang thứ hai."
