from app.embeddings import HashEmbedder


def test_hash_embedder_is_deterministic() -> None:
    embedder = HashEmbedder(dimension=32)
    first = embedder.embed(["Пропал домашний интернет"])[0]
    second = embedder.embed(["Пропал домашний интернет"])[0]

    assert first == second


def test_hash_embedder_returns_normalized_vectors() -> None:
    embedder = HashEmbedder(dimension=32)
    vector = embedder.embed(["Не работает мобильная связь"])[0]
    norm = sum(component * component for component in vector) ** 0.5

    assert round(norm, 6) == 1.0

