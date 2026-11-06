"""ESCO дағдыларының векторлық индексін құру (негізгі атау + балама атаулар).

Нәтиже: data/processed/esco_index_<model>.npz (float16). Кейін scripts.seed оны pgvector-ге жүктейді.
Іске қосу:  python -m scripts.build_index [--model intfloat/multilingual-e5-base] [--max-alt 8]
"""
from __future__ import annotations

import argparse
import time

import numpy as np

from app.config import get_settings
from app.services import esco_data
from app.services.embeddings import encode_passages
from app.services.esco_search import index_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=get_settings().embedding_model)
    ap.add_argument("--max-alt", type=int, default=8)
    args = ap.parse_args()

    skills = esco_data.load_skills()
    ids, labels, pref_flags = [], [], []
    for row in skills.itertuples():
        seen = set()
        for j, lab in enumerate([row.label, *row.alt_labels[: args.max_alt]]):
            key = lab.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            ids.append(row.esco_id)
            labels.append(lab.strip())
            pref_flags.append(j == 0)
    print(f"skills={len(skills)} label rows={len(labels)} model={args.model}")
    t = time.time()
    emb = encode_passages(labels, args.model, show_progress=True)
    print(f"encoded in {time.time() - t:.0f}s, dim={emb.shape[1]}")
    path = index_path(args.model)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, emb=emb.astype(np.float16), esco_ids=np.array(ids), labels=np.array(labels),
                        is_pref=np.array(pref_flags), pref_ids=skills["esco_id"].to_numpy(),
                        pref_labels=skills["label"].to_numpy(), model=np.array(args.model))
    print("saved", path)


if __name__ == "__main__":
    main()
