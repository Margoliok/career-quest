# Career Quest

**Қызметкердің дағдыларын талдап, оның кәсіби даму жолын ұсынатын AI-бағыттаушы**
ИИ-помощник, анализирующий навыки сотрудника и предлагающий дальнейшие шаги его профессионального развития.

Практическая часть дипломной работы (ЕНУ им. Л.Н. Гумилёва). Веб-платформа: сотрудник загружает резюме → система находит навыки (с фрагментом-доказательством и уровнем 1–4) и сопоставляет их с таксономией **ESCO** → считает разрыв с целевой ролью → рекомендует следующую роль (гибридная модель) → формирует **ИПР на 30/60/90 дней** с курсами → руководитель подтверждает навыки и согласует план. Все действия ИИ пишутся в журнал аудита.

> **Демо (GitHub Pages):** статическая версия интерфейса на данных, экспортированных из реального backend. Логин в один клик: `employee`, `employee2`, `manager`, `hr` (пароль `demo123`).

---

## Возможности

| Роль | Что доступно |
|---|---|
| Сотрудник | загрузка резюме (PDF/DOCX/TXT, каз/рус/англ), карта навыков с доказательствами, самооценка, радар «требование ↔ уровень», разрыв с ролью C(e,r) и приоритеты p_s, рекомендации ролей с разложением балла и ползунком α, ИПР 30/60/90 с курсами, отправка руководителю, ИИ-ассистент |
| Руководитель | сотрудники отдела, подтверждение/отклонение навыков и уровней, согласование или возврат ИПР с комментарием, тепловая карта навыков отдела |
| HR / L&D | обзор организации, тепловая карта, редактор профилей ролей (ESCO-поиск), каталог курсов, журнал аудита, экспорт CSV |

**ИИ-компонент.** LLM-агент (OpenAI, function calling) с 7 инструментами: `get_profile`, `extract_skills`, `search_esco`, `compute_gap`, `suggest_roles`, `find_courses`, `save_idp`. Ответы строятся только по данным инструментов. Есть guardrails: отказ отвечать на вопросы о зарплате, найме и увольнении, фильтр персональных данных перед отправкой в LLM, ограничение доступа только данными текущего сотрудника. Без ключа API система работает в **офлайн-режиме** (многоязычные эмбеддинги + глоссарий инструментов + шаблонный ИПР).

## Модели (формулы из главы 2.2)

- (1) `cos(u,v)` — сходство фразы и навыка ESCO (multilingual-e5 / bge-m3, pgvector HNSW)
- (2) `C(e,r) = Σ w_s·min(l_e,s / l_r,s, 1) / Σ w_s` — покрытие роли (essential = 1, optional = 0,5)
- (3) `p_s = w_s · max(l_r,s − l_e,s, 0)` — приоритет недостающего навыка
- (4) `P̂(r′|r) = (n(r→r′) + λ) / (n(r) + λ|R|)` — сглаженная вероятность перехода
- (5) `Score = α·P̃(r′|r) + (1−α)·C(e,r′)` — гибридный балл (P̃ нормирован по максимуму), α = 0,75 подобран на validation Karrierewege
- (6)–(11) P, R, F1, Recall@k, MRR, NDCG@k; (12) SUS

## Результаты экспериментов (реальные, воспроизводимые скриптами)

**Э3. Предсказание следующей профессии, Karrierewege test (56 815 траекторий, 3 039 профессий):**

| Метод | Recall@5 | Recall@10 | MRR | NDCG@10 |
|---|---|---|---|---|
| Самая популярная профессия | 0,251 | 0,350 | 0,176 | 0,203 |
| Только переходы (α = 1) | 0,356 | 0,481 | 0,250 | 0,292 |
| Только навыки (α = 0) | 0,181 | 0,203 | 0,151 | 0,159 |
| **Гибрид (α = 0,75, λ = 1)** | **0,386** | **0,502** | **0,259** | **0,308** |

Гибрид лучше обоих одиночных методов по всем метрикам → **H2 подтверждается** на этих данных.

**Э2. Извлечение навыков на 48 синтетических каз/рус профилях (test = 36), F1 по ESCO ID:**

| Метод | F1 (все) | F1 kk | F1 ru |
|---|---|---|---|
| Словарь по меткам ESCO (базовый) | 0,434 | 0,431 | 0,438 |
| Эмбеддинги по всей ESCO (e5-small) | 0,278 | 0,280 | 0,277 |
| Каталог ролей + e5-small + глоссарий | 0,522 | 0,561 | 0,478 |
| **Каталог ролей + bge-m3 + глоссарий (офлайн-режим)** | **0,716** | **0,709** | **0,723** |
| LLM + эмбеддинги + переранжирование | считается с `--llm` при наличии ключа | | |

Порог τ подбирается на dev-части (12 профилей). Эталонная разметка известна по построению шаблонов, LLM её не создаёт.

**Э1. SkillSpan test (англ., 3 507 предложений), span-F1:** словарный метод — strict 0,181 / loose 0,300. LLM-вариант запускается флагом `--llm`.

**Э5 (экспертная оценка ИПР) и SUS** проводятся с реальными участниками: скрипты генерируют слепые анкеты и считают итог (`e5_expert_forms.py`, `score_forms.py`). Заранее ни одно число не вписано.

Ограничения: профили синтетические (шаблоны), поэтому точность уровня завышена. Траектории Karrierewege описывают рынок труда Германии и используются только как приор. В ESCO нет казахского и русского языков. Ссылки на профстандарты РК (`prof_standard_ref`) заполняет автор.

## Данные

| Набор | Источник / лицензия | Как получен |
|---|---|---|
| ESCO v1.2.1 (13 939 навыков, 3 043 профессии, 126 051 связь) | European Commission, свободное использование | CSV в `data/esco/`. Сверка с официальным ESCO API (`selectedVersion=v1.2.1`): **25/25** профессий совпали полностью (`scripts/verify_esco.py`, `data/esco/meta.json`). Резервный вариант — `scripts/fetch_esco.py` (обход ESCO API) |
| Karrierewege | HuggingFace `ElenaSenger/Karrierewege` (лицензию проверить) | `scripts/load_karrierewege.py` скачивает около 900 МБ; в репозиторий не включён |
| O*NET 30.0 Technology Skills | CC BY 4.0 | `data/onet/`, сопоставление с ESCO — `data/onet/onet_to_esco.csv` |
| SkillSpan | MIT | `data/skillspan/` |
| Локальный кейс | автор | `data/local/`: 7 ролей (`roles_case.json`), экспертные переходы, глоссарий инструментов, 48 синтетических профилей |
| Каталог курсов | 29 записей, ссылки проверены (`scripts/verify_courses.py`) | Kaggle Learn, Stepik, Coursera, Microsoft Learn, Skills Enbek, внутренние (демо) |

## Запуск

### Docker (рекомендуется)
```bash
cp .env.example .env          # при наличии ключа укажите OPENAI_API_KEY
docker compose up --build     # db (PostgreSQL+pgvector), backend :8000, frontend :8080
```
При первом запуске backend сам строит векторный индекс ESCO, при необходимости скачивает Karrierewege (`KARRIEREWEGE=0` отключает) и заполняет базу. Интерфейс: http://localhost:8080, Swagger: http://localhost:8000/docs.

### Локально (разработка)
```bash
docker compose up -d db
cd backend && pip install -r requirements.txt
python -m scripts.build_index           # векторы ESCO
python -m scripts.load_karrierewege     # траектории (приор переходов)
python -m scripts.generate_profiles     # синтетические профили
python -m scripts.verify_courses        # проверка каталога курсов
python -m scripts.seed --reset          # заполнение БД
uvicorn app.main:app --port 8000
cd ../frontend && npm install && npm run dev   # http://localhost:5173
```

### Эксперименты, рисунки, приложения
```bash
cd backend
python -m scripts.experiments.e1_skillspan [--llm]
python -m scripts.experiments.e2_local_extraction [--llm]
python -m scripts.experiments.e3_next_role
python -m scripts.experiments.e5_expert_forms      # нужен OPENAI_API_KEY
python -m scripts.experiments.score_forms          # после заполнения анкет
python -m scripts.make_figures                     # reports/figures: рис. 5, 6, 11, 12, α-абляция
python -m scripts.make_appendix                    # reports/appendix: приложения 1–3
python -m scripts.export_demo                      # снимок для GitHub Pages
pytest -q tests                                    # 22 теста
```

## Соответствие разделам диплома

| Диплом | Где в проекте |
|---|---|
| Рис. 5 ESCO «data analyst» | `reports/figures/fig05_esco_data_analyst.png` |
| Рис. 6 конвейер извлечения | `reports/figures/fig06_extraction_pipeline.png` |
| Рис. 9–10 профиль и ИПР | скриншоты страниц «Менің профилім» и «Даму жоспары» |
| Рис. 11 F1 по методам и языкам | `reports/figures/fig11_e2_f1.png` |
| Рис. 12 карьерный путь (кейс) | `reports/figures/fig12_case_career_path.png` |
| Табл. 10 БД | `backend/app/models.py` |
| Табл. 12 API | Swagger `/docs`, `backend/app/api/` |
| Табл. 14 | `reports/tables/e3_next_role.csv` |
| Табл. 15–16 | `reports/tables/table15_expert.csv`, `table16_sus.csv` (после анкет) |
| Приложения 1–3 | `reports/appendix/*.md` |

## Структура
```
backend/app/      FastAPI: api/, services/ (extract, gap, recommend, idp, career), llm/ (провайдер, промпты, схемы), agent/
backend/scripts/  загрузка данных, seed, эксперименты, рисунки, приложения, экспорт демо
backend/tests/    pytest (формулы, извлечение, RBAC, workflow ИПР)
frontend/         React + Vite + TypeScript (каз/рус), демо-режим для GitHub Pages
data/             ESCO, O*NET, SkillSpan, локальный кейс, курсы
reports/          таблицы, рисунки, приложения, анкеты
```

Стек: Python 3.12 · FastAPI · SQLAlchemy · PostgreSQL 16 + pgvector · sentence-transformers (multilingual-e5-small, bge-m3) · OpenAI API · React 18 · Recharts · Docker.
