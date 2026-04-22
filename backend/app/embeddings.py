import hashlib
import math
from dataclasses import dataclass

import numpy as np

from .config import Settings


class EmbedderUnavailableError(RuntimeError):
    pass


class BaseEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class HashEmbedder(BaseEmbedder):
    def __init__(self, dimension: int) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        bucket = np.zeros(self.dimension, dtype=np.float32)
        tokens = [token for token in text.lower().split() if token]
        if not tokens:
            tokens = ["__empty__"]

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = -1.0 if digest[4] % 2 else 1.0
            weight = 1.0 + (digest[5] / 255.0)
            bucket[index] += sign * weight

        norm = np.linalg.norm(bucket)
        if norm == 0:
            return bucket.tolist()
        return (bucket / norm).tolist()


class TransformersEmbedder(BaseEmbedder):
    def __init__(self, model_name: str, expected_dim: int) -> None:
        self.model_name = model_name
        self.expected_dim = expected_dim
        self._tokenizer = None
        self._model = None

    def _lazy_load(self) -> None:
        if self._tokenizer is not None and self._model is not None:
            return

        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise EmbedderUnavailableError(
                "transformers backend requires torch and transformers packages"
            ) from exc

        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModel.from_pretrained(self.model_name)
        self._model.eval()
        self._torch = torch

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._lazy_load()
        encoded = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )

        with self._torch.no_grad():
            output = self._model(**encoded)

        attention_mask = encoded["attention_mask"].unsqueeze(-1)
        masked = output.last_hidden_state * attention_mask
        summed = masked.sum(dim=1)
        counts = attention_mask.sum(dim=1).clamp(min=1)
        pooled = summed / counts
        normalized = self._torch.nn.functional.normalize(pooled, p=2, dim=1)

        vectors = normalized.cpu().numpy().tolist()
        actual_dim = len(vectors[0]) if vectors else 0
        if actual_dim > self.expected_dim:
            raise EmbedderUnavailableError(
                f"Expected embedding dimension <= {self.expected_dim}, got {actual_dim}"
            )
        if actual_dim == self.expected_dim:
            return vectors

        padded_vectors: list[list[float]] = []
        padding = self.expected_dim - actual_dim
        for vector in vectors:
            padded_vectors.append([*vector, *([0.0] * padding)])
        return padded_vectors


@dataclass
class EmbedderState:
    ready: bool
    detail: str | None = None


class EmbedderManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._embedder: BaseEmbedder | None = None
        self.state = EmbedderState(ready=False, detail="Embedding model not loaded yet.")

    def warmup(self) -> None:
        try:
            self.get_embedder()
            self.state = EmbedderState(ready=True, detail=None)
        except Exception as exc:  # noqa: BLE001
            self.state = EmbedderState(ready=False, detail=str(exc))

    def get_embedder(self) -> BaseEmbedder:
        if self._embedder is not None:
            return self._embedder

        if self.settings.embedding_backend == "hash":
            self._embedder = HashEmbedder(self.settings.embedding_dim)
            return self._embedder

        if self.settings.embedding_backend == "transformers":
            self._embedder = TransformersEmbedder(
                self.settings.embedding_model_name,
                self.settings.embedding_dim,
            )
            return self._embedder

        raise EmbedderUnavailableError(
            f"Unsupported embedding backend: {self.settings.embedding_backend}"
        )

    def embed(self, text: str) -> list[float]:
        if not self.state.ready:
            self.warmup()

        if not self.state.ready:
            raise EmbedderUnavailableError(self.state.detail or "Embedding backend is not ready.")

        return self.get_embedder().embed([text])[0]
