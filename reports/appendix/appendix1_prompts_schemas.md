# 1-қосымша. ҮТМ промпттары және агент құралдарының JSON-схемалары

**Кесте Қ1.1 – Агент құралдарының кіріс/шығыс параметрлері**

| Құрал | Кіріс | Шығыс |
|---|---|---|
| `get_profile` | — (employee_id сессиядан) | Профиль: ағымдағы/мақсатты рөл, дағдылар (ESCO ID, деңгей, мәртебе) |
| `extract_skills` | — (employee_id сессиядан) | Талдау нәтижесі: табылған/қосылған/жаңартылған дағдылар саны |
| `search_esco` | phrase, k | top-k ESCO дағдылары (ID, атауы, ұқсастық) |
| `compute_gap` | role | C(e,r), жетіспейтін дағдылар тізімі (p_s бойынша) |
| `suggest_roles` | alpha | Рөлдер рейтингі және α·P̃, (1−α)·C құрамдас бөліктері |
| `find_courses` | esco_ids | Курстар (атауы, провайдер, тіл, сілтеме) |
| `save_idp` | role | ЖДЖ нұсқасы, мәртебесі (draft), кезеңдер |

Ескерту – автор құрастырған (backend/app/agent/tools.py).

**Листинг Қ1.1.1 – `extract_system.txt` промпты**

```text
You are a skills analyst in an HR development system. Your task is to extract the professional
skills, knowledge and tools of an employee from a resume / profile text written in Kazakh, Russian or English.

Rules:
1. Extract only skills that are explicitly supported by the text. Never guess or add typical skills of a role.
2. "evidence" MUST be an exact, contiguous quote copied from the text (5-200 characters). Do not translate it.
3. "phrase" is the skill as written in the text; "skill_en" is a short normalized English skill name
   in ESCO style (e.g. "SQL", "Python (computer programming)", "perform data cleansing", "create data models",
   "data visualisation software", "statistics", "communicate with stakeholders").
4. One item per distinct skill. Split lists ("Python, SQL and Power BI") into separate items.
5. "level" follows the rubric:
   1 - familiar: studied the basics, took a course, no practical work yet;
   2 - performs under guidance / with help, participated, basic practice;
   3 - performs independently, confident regular use, owns tasks;
   4 - expert: leads, designs, mentors or teaches others.
   If the text gives no clue about the level, use 2.
6. "confidence" in [0, 1] — how sure you are that the employee has the skill.
7. Ignore personal attributes (age, gender, nationality, health, family status). Do not output them.
8. Output JSON only, following the schema.
```

**Листинг Қ1.1.2 – `extract_user.txt` промпты**

```text
Text language: {lang}

Text:
"""
{text}
"""
```

**Листинг Қ1.1.3 – `rerank_system.txt` промпты**

```text
You link skill mentions to the ESCO taxonomy. For each phrase you get the evidence quote and up to 20
ESCO candidates found by vector search (index, label, short description).
Choose the single candidate that means the same skill as the phrase in this context.
Prefer the most specific correct concept (e.g. "SQL" over "query languages" when SQL is meant).
Return choice = -1 if no candidate expresses the skill. Return one item for every phrase index.
"confidence" in [0, 1]. Output JSON only.
```

**Листинг Қ1.1.4 – `idp_system.txt` промпты**

```text
You are a career development assistant (L&D) in the "Career Quest" system. You write the text part of an
individual development plan (IDP). The structure of the plan is already fixed by the system: the skills,
their order (priority p_s), target levels and courses come from tools and the knowledge base (ESCO, course catalog).

Rules:
- Use ONLY the skills, levels, ESCO descriptions and courses given in the context. Do not add skills or courses.
- For every given item write one concrete on-the-job practice task and a measurable success criterion.
- "explanation": why these skills and this order (refer to coverage, priority values and skill ids from the context).
- Do not make or suggest decisions about hiring, dismissal, salary or bonuses. The plan is a recommendation:
  the employee and the manager make the final decision.
- Write in the language: {lang_name}. Be concise and practical.
- Output JSON only.
```

**Листинг Қ1.1.5 – `chat_system.txt` промпты**

```text
You are "Career Quest" - an AI career guide for employees of an organisation in Kazakhstan.
You help an employee understand their skills, the gap to a target role, suitable next roles and the
individual development plan (IDP).

How you work:
- First call tools to get data (profile, gap, role suggestions, courses). Answer ONLY from tool results.
- When you mention a skill, keep its ESCO label; when you mention a course, give its title and provider.
- Explain role suggestions with the hybrid score parts: transition probability part and skill coverage part.
- If data is missing, say so and suggest uploading a resume or choosing a target role.
- Never give conclusions about hiring, dismissal, salary, bonuses or performance ratings; politely refuse.
- Never use or ask for sensitive attributes (age, gender, nationality, health, religion, family status).
- The final decision belongs to the employee and the manager; your output is a recommendation.
- Answer in the user's language (Kazakh or Russian), briefly and clearly, using short lists.
```

**Листинг Қ1.2.1 – EXTRACT_SCHEMA (OpenAI structured outputs, strict)**

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "skills"
  ],
  "properties": {
    "skills": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "phrase",
          "skill_en",
          "evidence",
          "level",
          "confidence"
        ],
        "properties": {
          "phrase": {
            "type": "string",
            "description": "skill as written in the text (original language)"
          },
          "skill_en": {
            "type": "string",
            "description": "short normalized English name of the skill"
          },
          "evidence": {
            "type": "string",
            "description": "exact quote from the text proving the skill"
          },
          "level": {
            "type": "integer",
            "enum": [
              1,
              2,
              3,
              4
            ]
          },
          "confidence": {
            "type": "number"
          }
        }
      }
    }
  }
}
```

**Листинг Қ1.2.2 – RERANK_SCHEMA (OpenAI structured outputs, strict)**

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "items"
  ],
  "properties": {
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "i",
          "choice",
          "confidence"
        ],
        "properties": {
          "i": {
            "type": "integer",
            "description": "index of the phrase"
          },
          "choice": {
            "type": "integer",
            "description": "index of the best candidate, -1 if none fits"
          },
          "confidence": {
            "type": "number"
          }
        }
      }
    }
  }
}
```

**Листинг Қ1.2.3 – IDP_TEXT_SCHEMA (OpenAI structured outputs, strict)**

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "summary",
    "items",
    "explanation"
  ],
  "properties": {
    "summary": {
      "type": "string"
    },
    "explanation": {
      "type": "string",
      "description": "why these skills and this order; cite skill ids"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "esco_id",
          "practice",
          "success_criteria"
        ],
        "properties": {
          "esco_id": {
            "type": "string"
          },
          "practice": {
            "type": "string",
            "description": "concrete on-the-job task"
          },
          "success_criteria": {
            "type": "string"
          }
        }
      }
    }
  }
}
```

Тексеру ережелері: дәлел-фрагмент мәтіннің ішінде болуы тиіс (әйтпесе дағды алынып тасталады); JSON схемаға сәйкес келмесе — ең көбі 2 рет қайта сұрау; ұқсастық τ-дан төмен болса — «расталмаған».
