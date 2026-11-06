"""ESCO бойынша векторлық іздеу: top-k үміткер дағдылар (pgvector немесе жадтағы numpy индексі).

Екі іске асырудың нәтижесі бірдей: pgvector HNSW индексі (API үшін) және дәл numpy іздеуі
(эксперименттерде жылдамдық үшін). Ұқсастық — (1) формула бойынша косинус.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from .embeddings import encode_queries


@dataclass
class Candidate:
    esco_id: str
    label: str
    matched_label: str
    sim: float


def index_path(model: str | None = None) -> Path:
    model = model or get_settings().embedding_model
    slug = model.split("/")[-1]
    return get_settings().cache_dir / f"esco_index_{slug}.npz"


class NumpyIndex:
    def __init__(self, path: Path):
        z = np.load(path, allow_pickle=True)
        self.emb = z["emb"].astype(np.float32)
        self.esco_ids = z["esco_ids"]
        self.labels = z["labels"]
        self.pref = dict(zip(z["pref_ids"], z["pref_labels"]))
        self.model = str(z["model"]) if "model" in z else get_settings().embedding_model

    def search_vectors(self, q: np.ndarray, k: int) -> list[list[Candidate]]:
        sims = q @ self.emb.T  # векторлар нормаланған → скаляр көбейтінді = косинус
        out: list[list[Candidate]] = []
        for row in sims:
            top = np.argpartition(-row, min(len(row) - 1, k * 6))[: k * 6]
            top = top[np.argsort(-row[top])]
            seen: dict[str, Candidate] = {}
            for i in top:
                eid = str(self.esco_ids[i])
                if eid not in seen:
                    seen[eid] = Candidate(eid, str(self.pref.get(eid, self.labels[i])), str(self.labels[i]), float(row[i]))
                if len(seen) >= k:
                    break
            out.append(list(seen.values()))
        return out

    def search(self, phrases: list[str], k: int | None = None) -> list[list[Candidate]]:
        k = k or get_settings().top_k
        if not phrases:
            return []
        return self.search_vectors(encode_queries(phrases, self.model), k)


@lru_cache(maxsize=2)
def numpy_index(model: str | None = None) -> NumpyIndex:
    return NumpyIndex(index_path(model))


class DomainIndex(NumpyIndex):
    """Ұйымның дағдылар каталогы бойынша индекс (рөл профильдеріндегі ESCO дағдылары).

    Офлайн режимде іздеу кеңістігін 13,9 мың ESCO дағдысынан ұйымға қатысты бірнеше жүз
    дағдыға дейін тарылтады — көптілді эмбеддингтердің жалған сәйкестіктері азаяды.
    """

    def __init__(self, esco_ids: list[str], model: str, max_alt: int = 8):
        import hashlib

        from . import esco_data
        from .embeddings import encode_passages

        ids_sorted = sorted(set(esco_ids))
        h = hashlib.sha1(("|".join(ids_sorted) + model + str(max_alt)).encode()).hexdigest()[:10]
        path = get_settings().cache_dir / f"domain_index_{model.split('/')[-1]}_{h}.npz"
        sk = esco_data.load_skills()
        sk = sk[sk.esco_id.isin(ids_sorted)]
        if not path.exists():
            ids, labels = [], []
            for r in sk.itertuples():
                for lab in dict.fromkeys([r.label, *r.alt_labels[:max_alt]]):
                    ids.append(r.esco_id)
                    labels.append(lab)
            emb = encode_passages(labels, model)
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(path, emb=emb.astype(np.float16), esco_ids=np.array(ids), labels=np.array(labels),
                                pref_ids=sk.esco_id.to_numpy(), pref_labels=sk.label.to_numpy(), model=np.array(model))
        super().__init__(path)
        self.model = model


@lru_cache(maxsize=8)
def domain_index(esco_ids: tuple[str, ...], model: str | None = None) -> DomainIndex:
    return DomainIndex(list(esco_ids), model or get_settings().offline_embedding_model)


class PgIndex:
    """pgvector арқылы іздеу (skill_labels кестесі, HNSW, cosine)."""

    def __init__(self, db: Session):
        self.db = db

    def search(self, phrases: list[str], k: int | None = None) -> list[list[Candidate]]:
        k = k or get_settings().top_k
        if not phrases:
            return []
        vecs = encode_queries(phrases)
        out: list[list[Candidate]] = []
        self.db.execute(text("SET LOCAL hnsw.ef_search = 200"))
        for v in vecs:
            rows = self.db.execute(text(
                """
                SELECT l.esco_id, s.label_en, l.label, 1 - (l.embedding <=> CAST(:q AS vector)) AS sim
                FROM skill_labels l JOIN skills s ON s.esco_id = l.esco_id
                ORDER BY l.embedding <=> CAST(:q AS vector)
                LIMIT :lim
                """), {"q": "[" + ",".join(f"{x:.6f}" for x in v) + "]", "lim": k * 6}).all()
            seen: dict[str, Candidate] = {}
            for eid, label, matched, sim in rows:
                if eid not in seen:
                    seen[eid] = Candidate(eid, label, matched, float(sim))
                if len(seen) >= k:
                    break
            out.append(list(seen.values()))
        return out
