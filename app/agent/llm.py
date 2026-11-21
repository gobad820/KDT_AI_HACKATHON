"""LLM 인터페이스. 에이전트 코드는 이 파일의 LLMClient 만 안다.

- 키는 환경변수(.env)로만 읽는다. 코드와 로그에 남기지 않는다.
- LLM_PROVIDER 가 비어 있으면 get_llm() 은 None 을 돌려주고, 서버는 대체 흐름으로 동작한다.
- openai 어댑터는 11/21 Gemini OpenAI 호환 주소(gemini-3.1-flash-lite)로 실제 호출을 확인했다.
  anthropic 어댑터는 실제 호출로 검증하지 못했다.
"""
from __future__ import annotations

import json
import os
import time
from typing import Callable, List, Optional, Protocol, Union

import httpx

RETRY_STATUS = {429, 500, 502, 503}
RETRY_WAIT_S = 1.0
# 한 번 시도에 기다리는 최대 시간. Gemini는 같은 요청도 2초~50초로 흔들려서(11/21 실측) 늦으면 다음 모델로 넘긴다
ATTEMPT_TIMEOUT_S = float(os.environ.get("LLM_ATTEMPT_TIMEOUT_S", "8"))
# 같은 공고에 같은 결과가 나오도록 응답 온도를 고정한다
TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0"))


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

    def __init__(self, api_key: str, model_name: str, base_url: str = "https://api.openai.com/v1",
                 fallbacks: Optional[List[str]] = None):
        self._key, self.model_name, self.base_url = api_key, model_name, base_url.rstrip("/")
        self.fallbacks = [m for m in (fallbacks or []) if m and m != model_name]

    def _post(self, model: str, system: str, user: str, schema: dict, timeout: float):
        """응답을 돌려준다. 시간 초과·연결 오류는 None(다음 모델로 넘길 수 있는 실패)."""
        body = {"model": model, "temperature": TEMPERATURE,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_schema", "json_schema": {"name": "output", "schema": schema}}}
        try:
            return httpx.post(f"{self.base_url}/chat/completions", json=body,
                              headers={"Authorization": f"Bearer {self._key}"}, timeout=timeout)
        except httpx.HTTPError:
            return None

    def complete_json(self, *, system: str, user: str, schema: dict, timeout_s: float = 20.0) -> dict:
        # 대체 모델이 있으면: 기본 → 대체 모델 차례로. 일시 오류·시간 초과면 기다리지 않고 바로 다음 모델로 넘긴다.
        # 대체 모델이 없으면: 일시 오류일 때 1초 뒤 같은 모델로 한 번 더.
        # 한 번 시도는 ATTEMPT_TIMEOUT_S까지만 기다리고(마지막 시도는 남은 시간 전부), 전체는 timeout_s 안에서만 쓴다.
        started = time.monotonic()
        plan = [self.model_name] + (self.fallbacks or [self.model_name])
        r, last_err = None, "LLM 호출 시간 부족"
        for i, model in enumerate(plan):
            remaining = timeout_s - (time.monotonic() - started)
            if remaining <= 1.0:
                break
            if i > 0 and model == self.model_name:   # 같은 모델 재시도는 시간이 넉넉할 때만
                if remaining - RETRY_WAIT_S < timeout_s / 2:
                    break
                time.sleep(RETRY_WAIT_S)
                remaining -= RETRY_WAIT_S
            last = i == len(plan) - 1
            r = self._post(model, system, user, schema, remaining if last else min(remaining, ATTEMPT_TIMEOUT_S))
            if r is None:
                last_err = "LLM 호출 시간 초과 또는 연결 실패"
                continue
            if r.status_code not in RETRY_STATUS:
                break
            last_err = f"LLM 응답 코드 {r.status_code}"
        if r is None:
            raise LLMUnavailable(last_err)
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
        fallbacks = [m.strip() for m in os.environ.get("LLM_MODEL_FALLBACKS", "").split(",") if m.strip()]
        return OpenAIClient(key, model, os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"), fallbacks)
    raise LLMUnavailable(f"지원하지 않는 LLM_PROVIDER: {provider} (anthropic, openai)")
