from __future__ import annotations

from typing import Any


class CrawlerError(Exception):
    code = "SPIDER.ERROR"
    retryable = False
    exit_code = 90

    def __init__(self, message: str, *, code: str | None = None, retryable: bool | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.retryable = self.retryable if retryable is None else retryable
        self.details = details or {}


class ParameterError(CrawlerError):
    code = "SPIDER.PARAMETER_ERROR"
    exit_code = 10


class ConfigurationError(CrawlerError):
    code = "SPIDER.CONFIGURATION_ERROR"
    exit_code = 20


class LoginError(CrawlerError):
    code = "SPIDER.LOGIN_ERROR"
    exit_code = 30


class CaptchaOrRiskError(CrawlerError):
    code = "SPIDER.CAPTCHA_OR_RISK"
    exit_code = 40


class NetworkError(CrawlerError):
    code = "SPIDER.NETWORK_ERROR"
    retryable = True
    exit_code = 50


class DatabaseError(CrawlerError):
    code = "SPIDER.DATABASE_ERROR"
    retryable = True
    exit_code = 60


class NoDataError(CrawlerError):
    code = "SPIDER.NO_DATA"
    exit_code = 70


class ParseError(CrawlerError):
    code = "SPIDER.PARSE_ERROR"
    exit_code = 80


class UnknownSpiderError(CrawlerError):
    code = "SPIDER.UNKNOWN_ERROR"
    exit_code = 90


def exit_code_for_error(exc: BaseException) -> int:
    return getattr(exc, "exit_code", 90)
