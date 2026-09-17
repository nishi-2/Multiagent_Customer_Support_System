from supportcommander.rag.similarity import cosine_similarity


def test_identical_vectors():
    score = cosine_similarity(
        [1.0, 0.0],
        [1.0, 0.0],
    )

    assert round(score, 6) == 1.0


def test_orthogonal_vectors():
    score = cosine_similarity(
        [1.0, 0.0],
        [0.0, 1.0],
    )

    assert round(score, 6) == 0.0