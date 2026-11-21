"""LLM 인터페이스. 에이전트 코드는 이 파일의 LLMClient 만 안다.

- 키는 환경변수(.env)로만 읽는다. 코드와 로그에 남기지 않는다.
- LLM_PROVIDER 가 비어 있으면 get_llm() 은 None 을 돌려주고, 서버는 대체 흐름으로 동작한다.
- anthropic, openai 어댑터는 공개 HTTP API 형식으로 썼지만 이 작업 환경에서는 실제 호출로 검증하지 못했다.
  키를 넣은 뒤 tests 밖에서 한 번 직접 호출해 확인한다 (docs/agent-spec.md 13장의 기록 대상).
"""
from __future__ import annotations

import json
import os
from typing import Callable, List, Optional, Protocol, Union

import httpx


class LLMUnavailable(Exception):
    """LLM 을 쓸 수 없음: 미설정, 네트워크, 시간 초과, 사용량 한도, 형식 오류."""


class LLMClient(Protocol):
    model_name: str

    def complete_json(self, *, system: str, user: str, schema: dict, timeout_s: float = 20.0) -> dict: ...


Responder = Union[dict, Exception, Callable[[str, str, dict], dict]]


class FakeLLM:
    """테스트용. responses 를 차례로 쓴다. 항목이 함수면 (system, user, schema) 로 불러 결과를 쓰고, 예외면 던진다."""

    def __init__(self, responses: Optional[List[Responder]] = None, fn: Optional[Callable] = None,
                 model_name: str = "fake-llm"):
        self.responses = list(responses or [])
        self.fn = fn
        self.model_name = model_name
        self.calls: List[dict] = []

    def complete_json(self, *, system: str, user: str, schema: dict, timeout_s: float = 20.0) -> dict:
        self.calls.append({"system": system, "user": user, "schema": schema})
        if self.fn is not None:
            out = self.fn(system, user, schema)
        elif self.responses:
            out = self.responses.pop(0)
        else:
            raise LLMUnavailable("FakeLLM 응답이 남아 있지 않음")
        if isinstance(out, Exception):
            raise out
        if callable(out):
            out = out(system, user, schema)
        return out


class AnthropicClient:
    """Anthropic Messages API. 도구 하나를 강제로 쓰게 해서 JSON 을 받는다."""

    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model_name: str, max_tokens: int = 2048):
        self._key, self.model_name, self.max_tokens = api_key, model_name, max_tokens

    def complete_json(self, *, system: str, user: str, schema: dict, timeout_s: float = 20.0) -> dict:
        body = {"model": self.model_name, "max_tokens": self.max_tokens, "system": system,
                "messages": [{"role": "user", "content": user}],
                "tools": [{"name": "output", "description": "결과를 이 형식으로 낸다", "input_schema": schema}],
                "tool_choice": {"type": "tool", "name": "output"}}
        headers = {"x-api-key": self._key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        try:
            r = httpx.post(self.URL, json=body, headers=headers, timeout=timeout_s)
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"LLM 호출 실패: {type(exc).__name__}") from None
        if r.status_code != 200:
            raise LLMUnavailable(f"LLM 응답 코드 {r.status_code}")
        for block in r.json().get("content", []):
            if block.get("type") == "tool_use":
                return block.get("input") or {}
        raise LLMUnavailable("LLM 응답에 결과가 없음")


class OpenAIClient:
    """OpenAI 호환 Chat Completions API. JSON 스키마 응답 형식을 쓴다."""

    def __init__(self, api_key: str, model_name: str, base_url: str = "https://api.openai.com/v1"):
        self._key, self.model_name, self.base_url = api_key, model_name, base_url.rstrip("/")

    def complete_json(self, *, system: str, user: str, schema: dict, timeout_s: float = 20.0) -> dict:
        body = {"model": self.model_name,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_schema", "json_schema": {"name": "output", "schema": schema}}}
        try:
            r = httpx.post(f"{self.base_url}/chat/completions", json=body,
                           headers={"Authorization": f"Bearer {self._key}"}, timeout=timeout_s)
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"LLM 호출 실패: {type(exc).__name__}") from None
        if r.status_code != 200:
            raise LLMUnavailable(f"LLM 응답 코드 {r.status_code}")
        try:
            return json.loads(r.json()["choices"][0]["message"]["content"])
        except (KeyError, IndexError, ValueError):
            raise LLMUnavailable("LLM 응답 형식 오류") from None


def get_llm() -> Optional[LLMClient]:
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if not provider:
        return None
    key, model = os.environ.get("LLM_API_KEY", "").strip(), os.environ.get("LLM_MODEL", "").strip()
    if not key or not model:
        raise LLMUnavailable("LLM_API_KEY 와 LLM_MODEL 을 .env 에 넣어야 한다")
    if provider == "anthropic":
        return AnthropicClient(key, model)
    if provider == "openai":
        return OpenAIClient(key, model, os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"))
    raise LLMUnavailable(f"지원하지 않는 LLM_PROVIDER: {provider} (anthropic, openai)")
