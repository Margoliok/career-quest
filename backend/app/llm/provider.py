"""ҮТМ провайдері: OpenAI Chat Completions (structured outputs + function calling), кэш, JSON валидациясы.

Кілт болмаса (немесе LLM_MODE=offline) get_provider() None қайтарады — жүйе офлайн режимде жұмыс істейді.
"""
from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from ..config import get_settings

log = logging.getLogger("careerquest.llm")
T = TypeVar("T", bound=BaseModel)
PROMPTS = Path(__file__).parent / "prompts"
LANG_NAMES = {"kk": "Kazakh (қазақ тілі)", "ru": "Russian (русский язык)", "en": "English"}


@lru_cache
def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.txt").read_text(encoding="utf-8")


class LLMError(RuntimeError):
    pass


class Cache(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, model: str, value: str) -> None: ...


class FileCache:
    """Эксперименттер үшін JSONL кэш (қайта іске қосқанда токен жұмсалмайды)."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, str] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.data[rec["k"]] = rec["v"]

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, model: str, value: str) -> None:
        self.data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"k": key, "m": model, "v": value}, ensure_ascii=False) + "\n")


class DBCache:
    def __init__(self, db):
        self.db = db

    def get(self, key: str) -> str | None:
        from ..models import LLMCache

        row = self.db.get(LLMCache, key)
        return row.response if row else None

    def set(self, key: str, model: str, value: str) -> None:
        from ..models import LLMCache

        self.db.merge(LLMCache(key=key, model=model, response=value))
        self.db.commit()


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str | None = None, cache: Cache | None = None):
        from openai import OpenAI

        s = get_settings()
        self.model = model or s.openai_model
        self.client = OpenAI(api_key=s.openai_api_key, base_url=s.openai_base_url or None, timeout=120)
        self.cache = cache
        self.max_retries = s.llm_max_retries
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0, "cache_hits": 0}

    def with_cache(self, cache: Cache | None) -> "OpenAIProvider":
        clone = object.__new__(OpenAIProvider)
        clone.__dict__.update(self.__dict__)
        clone.cache = cache
        return clone

    def _key(self, payload: dict) -> str:
        raw = json.dumps({"model": self.model, **payload}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _track(self, resp) -> None:
        self.usage["calls"] += 1
        if getattr(resp, "usage", None):
            self.usage["prompt_tokens"] += resp.usage.prompt_tokens or 0
            self.usage["completion_tokens"] += resp.usage.completion_tokens or 0

    def json(self, schema_name: str, schema: dict, model_cls: type[T], system: str, user: str,
             validate: Any = None) -> T:
        """JSON-схема бойынша жауап алу; схемаға/тексеруге сәйкес келмесе — ең көбі max_retries рет қайта сұрау."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        key = self._key({"schema": schema_name, "messages": messages})
        if self.cache and (hit := self.cache.get(key)):
            self.usage["cache_hits"] += 1
            return model_cls.model_validate_json(hit)
        last_err = None
        for attempt in range(self.max_retries + 1):
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages, temperature=0, seed=42,
                response_format={"type": "json_schema",
                                 "json_schema": {"name": schema_name, "schema": schema, "strict": True}},
            )
            self._track(resp)
            content = resp.choices[0].message.content or ""
            try:
                obj = model_cls.model_validate_json(content)
                if validate:
                    validate(obj)
                if self.cache:
                    self.cache.set(key, self.model, content)
                return obj
            except (ValidationError, ValueError) as exc:
                last_err = exc
                log.warning("LLM JSON validation failed (attempt %s): %s", attempt + 1, exc)
                messages = messages[:2] + [
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": f"The JSON is invalid: {exc}. Return corrected JSON only."},
                ]
        raise LLMError(f"LLM output invalid after retries: {last_err}")

    def chat(self, messages: list[dict], tools: list[dict] | None = None):
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=0.2,
            tools=tools or None, tool_choice="auto" if tools else None,
        )
        self._track(resp)
        return resp.choices[0].message


def get_provider(cache: Cache | None = None) -> OpenAIProvider | None:
    s = get_settings()
    if not s.llm_enabled:
        return None
    return OpenAIProvider(cache=cache)
