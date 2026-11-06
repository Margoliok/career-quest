#!/bin/sh
set -e
# Бірінші іске қосу: ESCO векторлық индексі жоқ болса құру, дерекқорды толтыру (идемпотентті)
if ! ls /data/processed/esco_index_*.npz >/dev/null 2>&1; then
  python -m scripts.build_index
fi
# Karrierewege (~900 MB) — рөлдер арасындағы ауысулар приоры үшін; KARRIEREWEGE=0 болса өткізіледі
if [ "${KARRIEREWEGE:-1}" = "1" ] && [ ! -f /data/processed/kw_train.csv.gz ]; then
  python -m scripts.load_karrierewege --kw-dir /data/karrierewege || echo "Karrierewege skipped"
fi
python -m scripts.seed
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
