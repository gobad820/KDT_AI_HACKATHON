"""API 오류. 형식과 값 목록은 docs/api-spec.md 7장."""
from __future__ import annotations


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, fallback: str):
        super().__init__(message)
        self.status, self.code, self.message, self.fallback = status, code, message, fallback


def invalid_input(message: str) -> ApiError:
    return ApiError(400, "INVALID_INPUT", message, "fix_input")


def posting_unreadable(message: str) -> ApiError:
    return ApiError(422, "POSTING_UNREADABLE", message, "manual_input")


def rate_limited(message: str) -> ApiError:
    return ApiError(429, "RATE_LIMITED", message, "sample_mode")


def llm_unavailable(message: str) -> ApiError:
    return ApiError(503, "LLM_UNAVAILABLE", message, "manual_input")
