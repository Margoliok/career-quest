"""Көптілді эмбеддингтер (multilingual-e5): қазақ/орыс фразалары ағылшын ESCO белгілерімен бір кеңістікте."""
from __future__ import annotations

import threading
from functools import lru_cache

import numpy as np

from ..config import get_settings

_lock = threading.Lock()


@lru_cache(maxsize=2)
def _model(name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name, device="cpu")


def model_name() -> str:
    return get_settings().embedding_model


def _encode(texts: list[str], prefix: str, name: str | None = None, batch_size: int = 128,
            show_progress: bool = False) -> np.ndarray:
    name = name or model_name()
    if not texts:
        return np.zeros((0, get_settings().embedding_dim), dtype=np.float32)
    # e5 моделі сұрау мен құжатты "query:" / "passage:" префикстерімен ажыратады
    items = [f"{prefix}{t}" for t in texts] if "e5" in name else texts
    with _lock:
        vec = _model(name).encode(items, batch_size=batch_size, normalize_embeddings=True,
                                  show_progress_bar=show_progress, convert_to_numpy=True)
    return vec.astype(np.float32)


def encode_queries(texts: list[str], name: str | None = None) -> np.ndarray:
    return _encode(texts, "query: ", name)


def encode_passages(texts: list[str], name: str | None = None, show_progress: bool = False) -> np.ndarray:
    return _encode(texts, "passage: ", name, show_progress=show_progress)


def cosine(u: np.ndarray, v: np.ndarray) -> float:
    """(1) формула: cos(u, v) = u·v / (‖u‖·‖v‖)."""
    nu, nv = np.linalg.norm(u), np.linalg.norm(v)
    if nu == 0 or nv == 0:
        return 0.0
    return float(np.dot(u, v) / (nu * nv))
