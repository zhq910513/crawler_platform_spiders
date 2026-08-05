# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import urlparse

from crawler_foundation.core.context import TaskContext
from crawler_foundation.core.exceptions import ConfigurationError, LoginError, NetworkError, ParseError
from plugins.db.mongo_client import MongoClientWrapper, MongoConfig


@dataclass(slots=True)
class OilchemAccount:
    """隆众资讯账号入参。

    HAR 复盘后的可用登录方式：
    1. token/cookieString 登录态校验；
    2. username + password + 网易易盾 validate 表单登录。

    注意：网易易盾 validate 不是普通图片验证码，本基类只接收外部已经拿到的 validate，
    不在纯 requests 流程里伪造或绕过验证码。
    """

    username: str
    password: str = ""
    token: str = ""
    cookie_string: str = ""
    captcha_validate: str = ""
    captcha_id: str = ""
    target_url: str = ""
    remember: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None = None, **kwargs: Any) -> "OilchemAccount":
        data: dict[str, Any] = {}
        if payload:
            account = payload.get("account")
            if isinstance(account, dict):
                data.update(account)
            data.update({k: v for k, v in payload.items() if k not in {"account"}})
        data.update({k: v for k, v in kwargs.items() if v not in (None, "")})
        username = str(
            data.get("username")
            or data.get("user")
            or data.get("accountName")
            or os.getenv("OILCHEM_USERNAME")
            or ""
        ).strip()
        password = str(data.get("password") or data.get("pwd") or os.getenv("OILCHEM_PASSWORD") or "").strip()
        token = str(data.get("token") or data.get("jwt") or os.getenv("OILCHEM_TOKEN") or "").strip()
        cookie_string = str(
            data.get("cookieString")
            or data.get("cookie_string")
            or data.get("cookie")
            or os.getenv("OILCHEM_COOKIE_STRING")
            or ""
        ).strip()
        captcha_validate = str(
            data.get("captchaValidate")
            or data.get("captcha_validate")
            or data.get("NECaptchaValidate")
            or data.get("neCaptchaValidate")
            or data.get("vcode")
            or os.getenv("OILCHEM_CAPTCHA_VALIDATE")
            or ""
        ).strip()
        captcha_id = str(
            data.get("captchaId")
            or data.get("captcha_id")
            or os.getenv("OILCHEM_CAPTCHA_ID")
            or OilchemBase.default_captcha_id
        ).strip()
        target_url = str(
            data.get("target")
            or data.get("targetUrl")
            or data.get("target_url")
            or os.getenv("OILCHEM_TARGET_URL")
            or OilchemBase.default_target_url
        ).strip()
        remember = cls._to_bool(data.get("remember", data.get("rememberPassword", os.getenv("OILCHEM_REMEMBER_PASSWORD", "false"))))
        if not username:
            raise ConfigurationError("oilchem 登录缺少 username，请通过任务参数 account.username 或 OILCHEM_USERNAME 传入")
        return cls(
            username=username,
            password=password,
            token=token,
            cookie_string=cookie_string,
            captcha_validate=captcha_validate,
            captcha_id=captcha_id,
            target_url=target_url,
            remember=remember,
        )

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True, slots=True)
class OilchemCacheKeys:
    user_token_key: str
    common_token_key: str
    user_cookie_key: str
    legacy_cookie_key: str
    mongo_name: str

    @classmethod
    def for_username(cls, username: str) -> "OilchemCacheKeys":
        # 保留历史 Redis key，避免迁移后旧缓存全部失效。
        return cls(
            user_token_key=f"oilchem_jwt_{username}",
            common_token_key="oilchem_jwt",
            user_cookie_key=f"oilchem_cookie_{username}",
            legacy_cookie_key="oilchem_cookie",
            mongo_name=f"oilchem_cookie_{username}",
        )


class OilchemBase:
    token_cookie_name = "_member_user_tonken_"
    default_captcha_id = "a17cc715e78a4afc8c43cd85da9d7254"
    home_url = "https://dc.oilchem.net/page/"
    default_target_url = "https://dc.oilchem.net/page/#/index"
    check_login_url = "https://dc.oilchem.net/ndc/common/getUserId"
    passport_check_token_url = "https://passport.oilchem.net/member/login/checkToken"
    login_url = "https://passport.oilchem.net/member/login/login"

    def __init__(self, context: TaskContext, *, account: OilchemAccount | None = None) -> None:
        self.context = context
        self.logger = context.logger.bind(platform="oilchem")
        self.account = account
        self.impersonate = os.getenv("OILCHEM_IMPERSONATE", "chrome")
        self.timeout_seconds = int(float(os.getenv("OILCHEM_TIMEOUT_SECONDS", "60")))
        self.session = self.create_session()

    def create_session(self):
        """创建会话，优先使用 curl_cffi；不可用时退回 requests。"""

        try:
            from curl_cffi import requests as curl_requests  # type: ignore

            return curl_requests.Session(impersonate=self.impersonate)
        except Exception:
            from plugins.http.session import create_session

            self.logger.warning("curl_cffi 不可用，已退回 requests.Session；若目标站点依赖 TLS 指纹，建议安装 curl_cffi", event="oilchem_session_fallback")
            return create_session(timeout_seconds=float(os.getenv("OILCHEM_TIMEOUT_SECONDS", "60")), retries=1)

    @staticmethod
    def parse_cookie_string(cookie_string: str) -> dict[str, str]:
        cookie = SimpleCookie()
        cookie.load(cookie_string or "")
        return {key: morsel.value for key, morsel in cookie.items()}

    @staticmethod
    def cookie_dict_to_string(cookies: dict[str, str]) -> str:
        return ";".join(f"{key}={value}" for key, value in cookies.items() if value not in (None, ""))

    @staticmethod
    def _safe_cookie_dict(cookies: dict[str, Any]) -> dict[str, str]:
        """去掉不应持久化的敏感/无用字段。token 会单独保存，密码 cookie 永不保存。"""

        blocked = {"_pass"}
        result: dict[str, str] = {}
        for key, value in cookies.items():
            if not key or key in blocked or value in (None, ""):
                continue
            result[str(key)] = str(value)
        return result

    def _session_cookie_dict(self) -> dict[str, str]:
        jar = getattr(self.session, "cookies", None)
        if jar is None:
            return {}
        try:
            if hasattr(jar, "get_dict"):
                return {str(k): str(v) for k, v in jar.get_dict().items()}
            return {str(cookie.name): str(cookie.value) for cookie in jar}
        except Exception:
            return {}

    def _merge_cookie_to_session(self, cookies: dict[str, str], *, domain: str = ".oilchem.net") -> None:
        jar = getattr(self.session, "cookies", None)
        if jar is None:
            return
        for key, value in cookies.items():
            try:
                jar.set(key, value, domain=domain, path="/")
            except Exception:
                try:
                    jar.set(key, value)
                except Exception:
                    pass

    def extract_token_from_cookie_cache(self, cookie_cache: Any) -> str | None:
        if not cookie_cache:
            return None
        if isinstance(cookie_cache, bytes):
            cookie_cache = cookie_cache.decode("utf-8", errors="ignore")
        if isinstance(cookie_cache, dict):
            cookie_data = cookie_cache.get("cookies") if isinstance(cookie_cache.get("cookies"), dict) else cookie_cache
            token = cookie_data.get(self.token_cookie_name) if isinstance(cookie_data, dict) else None
            return str(token).strip() if token else None
        if isinstance(cookie_cache, str):
            try:
                data = json.loads(cookie_cache)
                token = self.extract_token_from_cookie_cache(data)
                if token:
                    return token
            except Exception:
                pass
            if self.token_cookie_name in cookie_cache:
                return self.parse_cookie_string(cookie_cache).get(self.token_cookie_name)
        return None

    def token_from_input(self, account: OilchemAccount) -> str | None:
        if account.token:
            return self.normalize_token(account.token)
        if account.cookie_string:
            cookie_dict = self.parse_cookie_string(account.cookie_string)
            self._merge_cookie_to_session(self._safe_cookie_dict(cookie_dict))
            token = self.extract_token_from_cookie_cache(cookie_dict) or self.extract_token_from_cookie_cache(account.cookie_string)
            if token:
                return self.normalize_token(token)
            raise LoginError(f"oilchem cookieString 中不包含 {self.token_cookie_name}", details={"username": account.username})
        return None

    def normalize_token(self, token_or_cookie: str) -> str:
        value = str(token_or_cookie or "").strip()
        if not value:
            raise LoginError("oilchem token 不能为空")
        if value.startswith(f"{self.token_cookie_name}="):
            value = value.split("=", 1)[1].strip()
        if ";" in value:
            parsed = self.parse_cookie_string(value)
            value = parsed.get(self.token_cookie_name, value)
        if not value:
            raise LoginError("oilchem token 解析后为空")
        return value

    @staticmethod
    def md5_password(password: str) -> str:
        value = str(password or "").strip()
        if not value:
            raise LoginError("oilchem password 不能为空")
        if re.fullmatch(r"[0-9a-fA-F]{32}", value):
            return value.lower()
        return hashlib.md5(value.encode("utf-8")).hexdigest()

    def common_browser_headers(self) -> dict[str, str]:
        return {
            "User-Agent": os.getenv(
                "OILCHEM_USER_AGENT",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
            ),
            "sec-ch-ua": os.getenv("OILCHEM_SEC_CH_UA", '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"'),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

    def page_headers(self) -> dict[str, str]:
        headers = self.common_browser_headers()
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            }
        )
        return headers

    def login_form_headers(self) -> dict[str, str]:
        headers = self.common_browser_headers()
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Cache-Control": "no-cache",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://dc.oilchem.net",
                "Pragma": "no-cache",
                "Referer": "https://dc.oilchem.net/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-site",
            }
        )
        return headers

    def api_headers(self, token: str) -> dict[str, str]:
        headers = self.common_browser_headers()
        headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "application/json",
                "Origin": "https://dc.oilchem.net",
                "Pragma": "no-cache",
                "Referer": "https://dc.oilchem.net/page/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "token": f"{self.token_cookie_name}={token}",
            }
        )
        return headers

    # 兼容旧业务调用名。
    def generate_headers(self, token: str) -> dict[str, str]:
        return self.api_headers(token)

    def bootstrap_home(self) -> None:
        try:
            try:
                self.session.get(self.home_url, headers=self.page_headers(), timeout=self.timeout_seconds, impersonate=self.impersonate)
            except TypeError:
                self.session.get(self.home_url, headers=self.page_headers(), timeout=self.timeout_seconds)
        except Exception as exc:
            # 首页预热失败不直接判定登录失败，后续 login/check 会给出明确错误。
            self.logger.warning("oilchem 首页预热失败，继续尝试登录", event="oilchem_bootstrap_failed", error=str(exc))

    def build_login_form(self, account: OilchemAccount) -> dict[str, str]:
        if not account.password:
            raise LoginError("oilchem password 不能为空，用户名密码登录必须传入 password")
        if not account.captcha_validate:
            raise LoginError(
                "oilchem 用户名密码登录缺少网易易盾 validate，请先通过浏览器/打码服务获取 NECaptchaValidate",
                details={"captchaId": account.captcha_id or self.default_captcha_id},
            )
        password_md5 = self.md5_password(account.password)
        return {
            "username": account.username,
            "password": password_md5,
            "agree": "on",
            "NECaptchaValidate": account.captcha_validate,
            "target": account.target_url or self.default_target_url,
            # HAR 里 errorPaw 与 password 均为 32 位 md5；这里默认不回传明文密码。
            "errorPaw": f"({password_md5})",
            "captchaId": account.captcha_id or self.default_captcha_id,
            "vcode": account.captcha_validate,
        }

    def password_login(self, account: OilchemAccount, *, check: bool = True, persist: bool = True) -> dict[str, Any]:
        data = self.build_login_form(account)
        self.bootstrap_home()
        try:
            try:
                response = self.session.post(
                    self.login_url,
                    headers=self.login_form_headers(),
                    data=data,
                    timeout=self.timeout_seconds,
                    allow_redirects=False,
                    impersonate=self.impersonate,
                )
            except TypeError:
                response = self.session.post(
                    self.login_url,
                    headers=self.login_form_headers(),
                    data=data,
                    timeout=self.timeout_seconds,
                    allow_redirects=False,
                )
        except Exception as exc:
            raise NetworkError("oilchem 表单登录请求失败", details={"url": self.login_url}) from exc

        status_code = int(getattr(response, "status_code", 0) or 0)
        location = str(getattr(response, "headers", {}).get("Location") or getattr(response, "headers", {}).get("location") or "")
        token = self.extract_login_token(response)
        if not token:
            body = getattr(response, "text", "") or ""
            raise LoginError(
                "oilchem 表单登录未返回 token，可能是账号密码错误、验证码失效或被风控拦截",
                details={"statusCode": status_code, "locationHost": urlparse(location).netloc if location else "", "bodyPreview": body[:300]},
            )
        self._merge_cookie_to_session({self.token_cookie_name: token})
        user_id = self.check_login_by_token(token) if check else None
        cookie_dict = self._safe_cookie_dict(self._session_cookie_dict())
        cookie_dict[self.token_cookie_name] = token
        if persist:
            self.save_token(account.username, token, cookie_dict=cookie_dict)
        self.account = account
        return {
            "username": account.username,
            "userId": str(user_id or ""),
            "checked": bool(check),
            "persisted": bool(persist),
            "loginMode": "password",
            "captchaId": account.captcha_id or self.default_captcha_id,
            "redirectLocation": location,
            "cookieNames": sorted(cookie_dict.keys()),
            "cacheKeys": self.safe_cache_key_info(account.username),
        }

    def extract_login_token(self, response: Any) -> str | None:
        # 1. response.cookies
        try:
            cookies = getattr(response, "cookies", None)
            if cookies is not None:
                if hasattr(cookies, "get"):
                    token = cookies.get(self.token_cookie_name)
                    if token:
                        return self.normalize_token(str(token))
                if hasattr(cookies, "get_dict"):
                    token = cookies.get_dict().get(self.token_cookie_name)
                    if token:
                        return self.normalize_token(str(token))
        except Exception:
            pass
        # 2. session.cookies
        token = self._session_cookie_dict().get(self.token_cookie_name)
        if token:
            return self.normalize_token(token)
        # 3. Set-Cookie header
        try:
            headers = getattr(response, "headers", {}) or {}
            set_cookie = headers.get("Set-Cookie") or headers.get("set-cookie") or ""
            token = self.extract_token_from_cookie_cache(set_cookie)
            if token:
                return self.normalize_token(token)
        except Exception:
            pass
        return None

    def post_json(self, url: str, json_data: dict[str, Any], *, token: str, timeout: int = 60) -> dict[str, Any]:
        headers = self.api_headers(token)
        self._merge_cookie_to_session({self.token_cookie_name: token})
        try:
            try:
                response = self.session.post(url=url, headers=headers, json=json_data, timeout=timeout, impersonate=self.impersonate)
            except TypeError:
                response = self.session.post(url=url, headers=headers, json=json_data, timeout=timeout)
        except Exception as exc:
            raise NetworkError("oilchem POST 请求失败", details={"url": url}) from exc
        return self.parse_json_response(response, url=url)

    def get_json(self, url: str, *, token: str, timeout: int = 60) -> dict[str, Any]:
        headers = self.api_headers(token)
        self._merge_cookie_to_session({self.token_cookie_name: token})
        try:
            try:
                response = self.session.get(url=url, headers=headers, timeout=timeout, impersonate=self.impersonate)
            except TypeError:
                response = self.session.get(url=url, headers=headers, timeout=timeout)
        except Exception as exc:
            raise NetworkError("oilchem GET 请求失败", details={"url": url}) from exc
        return self.parse_json_response(response, url=url)

    def parse_json_response(self, response: Any, *, url: str = "") -> dict[str, Any]:
        status_code = int(getattr(response, "status_code", 0) or 0)
        text = getattr(response, "text", "") or ""
        if status_code != 200:
            raise NetworkError("oilchem 请求返回非 200", details={"url": url, "statusCode": status_code, "bodyPreview": text[:300]})
        if "<html" in text[:300].lower() or "<!doctype html" in text[:300].lower():
            raise LoginError("oilchem 返回 HTML，疑似登录态失效或被风控拦截", details={"url": url, "bodyPreview": text[:300]})
        try:
            payload = response.json()
        except Exception as exc:
            raise ParseError("oilchem JSON 解析失败", details={"url": url, "bodyPreview": text[:300]}) from exc
        if not isinstance(payload, dict):
            raise ParseError("oilchem JSON 根节点不是对象", details={"url": url})
        return payload

    def login(self, account: OilchemAccount, *, check: bool = True, persist: bool = True) -> dict[str, Any]:
        """登录/校验入口。

        优先级：任务参数 token/cookieString > 缓存 token > username/password/NECaptchaValidate 表单登录。
        """

        token = self.token_from_input(account) or self.load_cached_token(account.username)
        if token:
            self._merge_cookie_to_session({self.token_cookie_name: token})
            user_id = self.check_login_by_token(token) if check else None
            if persist:
                cookie_dict = self._safe_cookie_dict(self._session_cookie_dict())
                cookie_dict[self.token_cookie_name] = token
                self.save_token(account.username, token, cookie_dict=cookie_dict)
            self.account = account
            return {
                "username": account.username,
                "userId": str(user_id or ""),
                "checked": bool(check),
                "persisted": bool(persist),
                "loginMode": "token",
                "cacheKeys": self.safe_cache_key_info(account.username),
            }
        if account.password:
            return self.password_login(account, check=check, persist=persist)
        raise LoginError("oilchem token 不存在，请传入 token/cookieString，或传入 password + NECaptchaValidate 执行表单登录", details={"username": account.username})

    def check_login_by_token(self, token: str) -> str | None:
        result = self.get_json(self.check_login_url, token=token, timeout=int(os.getenv("OILCHEM_CHECK_TIMEOUT_SECONDS", "30")))
        user_id = result.get("response")
        if user_id and str(user_id) != "0":
            return str(user_id)
        raise LoginError("oilchem token 校验失败", details={"response": result})

    def redis_client(self):
        redis_url = os.getenv("REDIS_URL") or os.getenv("OILCHEM_REDIS_URL")
        redis_host = os.getenv("REDIS_HOST") or os.getenv("OILCHEM_REDIS_HOST")
        if not redis_url and not redis_host:
            return None
        try:
            import redis

            if redis_url:
                return redis.Redis.from_url(redis_url, decode_responses=True)
            return redis.Redis(
                host=redis_host,
                port=int(os.getenv("REDIS_PORT", os.getenv("OILCHEM_REDIS_PORT", "6379"))),
                db=int(os.getenv("REDIS_DB", os.getenv("OILCHEM_REDIS_DB", "0"))),
                username=os.getenv("REDIS_USERNAME") or os.getenv("OILCHEM_REDIS_USERNAME") or None,
                password=os.getenv("REDIS_PASSWORD") or os.getenv("OILCHEM_REDIS_PASSWORD") or None,
                socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "30")),
                decode_responses=True,
            )
        except Exception as exc:
            self.logger.warning("oilchem Redis 初始化失败，将跳过 Redis 缓存", event="oilchem_redis_init_failed", error=str(exc))
            return None

    def mongo_wrapper(self) -> MongoClientWrapper | None:
        uri = os.getenv("OILCHEM_MONGO_URI") or os.getenv("MONGO_URI")
        if not uri:
            return None
        try:
            return MongoClientWrapper(MongoConfig(uri=uri))
        except Exception as exc:
            self.logger.warning("oilchem Mongo 初始化失败，将跳过 Mongo 缓存", event="oilchem_mongo_init_failed", error=str(exc))
            return None

    def load_cached_token(self, username: str) -> str | None:
        keys = OilchemCacheKeys.for_username(username)
        redis_client = self.redis_client()
        if redis_client is not None:
            for key in (keys.user_token_key, keys.common_token_key, keys.user_cookie_key, keys.legacy_cookie_key):
                try:
                    value = redis_client.get(key)
                    token = self.extract_token_from_cookie_cache(value) or (self.normalize_token(value) if value and self.token_cookie_name not in str(value) else None)
                    if token:
                        self.logger.info("oilchem 从 Redis 读取 token 成功", event="oilchem_cache_hit", cache="redis", key=key, username=username)
                        try:
                            redis_client.close()
                        except Exception:
                            pass
                        return token
                except Exception as exc:
                    self.logger.warning("oilchem 读取 Redis token 失败", event="oilchem_redis_get_failed", key=key, error=str(exc))
            try:
                redis_client.close()
            except Exception:
                pass
        wrapper = self.mongo_wrapper()
        if wrapper is None:
            return None
        try:
            db_name = os.getenv("OILCHEM_MONGO_DB", os.getenv("MONGO_DB", "cookie"))
            coll_name = os.getenv("OILCHEM_MONGO_COLLECTION", "cookies")
            coll = wrapper.client[db_name][coll_name]
            doc = coll.find_one({"name": keys.mongo_name}) or coll.find_one({"username": username, "platform": "oilchem"})
            if doc:
                for field in ("token", "cookie", "cookies"):
                    token = self.extract_token_from_cookie_cache(doc.get(field)) or (self.normalize_token(doc.get(field)) if doc.get(field) and field == "token" else None)
                    if token:
                        cookie_value = doc.get("cookies") or doc.get("cookie")
                        if isinstance(cookie_value, dict):
                            self._merge_cookie_to_session(self._safe_cookie_dict(cookie_value))
                        elif isinstance(cookie_value, str):
                            self._merge_cookie_to_session(self._safe_cookie_dict(self.parse_cookie_string(cookie_value)))
                        self.logger.info("oilchem 从 Mongo 读取 token 成功", event="oilchem_cache_hit", cache="mongo", username=username)
                        return token
        except Exception as exc:
            self.logger.warning("oilchem 读取 Mongo token 失败", event="oilchem_mongo_get_failed", error=str(exc))
        finally:
            wrapper.close()
        return None

    def save_token(self, username: str, token: str, *, cookie_dict: dict[str, str] | None = None) -> None:
        token = self.normalize_token(token)
        keys = OilchemCacheKeys.for_username(username)
        cookies = self._safe_cookie_dict(cookie_dict or {})
        cookies[self.token_cookie_name] = token
        cookie_string = self.cookie_dict_to_string(cookies)
        redis_client = self.redis_client()
        if redis_client is not None:
            for key, value in (
                (keys.user_token_key, token),
                (keys.common_token_key, token),
                (keys.user_cookie_key, json.dumps({"cookies": cookies}, ensure_ascii=False)),
                (keys.legacy_cookie_key, json.dumps({"cookies": cookies}, ensure_ascii=False)),
            ):
                try:
                    redis_client.set(key, value)
                except Exception as exc:
                    self.logger.warning("oilchem 写入 Redis token 失败", event="oilchem_redis_set_failed", key=key, error=str(exc))
            try:
                redis_client.close()
            except Exception:
                pass
        wrapper = self.mongo_wrapper()
        if wrapper is not None:
            try:
                db_name = os.getenv("OILCHEM_MONGO_DB", os.getenv("MONGO_DB", "cookie"))
                coll_name = os.getenv("OILCHEM_MONGO_COLLECTION", "cookies")
                coll = wrapper.client[db_name][coll_name]
                coll.update_one(
                    {"name": keys.mongo_name},
                    {
                        "$set": {
                            "name": keys.mongo_name,
                            "platform": "oilchem",
                            "username": username,
                            "url": self.default_target_url,
                            "cookie": cookie_string,
                            "cookies": cookies,
                            "token": token,
                            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    },
                    upsert=True,
                )
            except Exception as exc:
                self.logger.warning("oilchem 写入 Mongo token 失败", event="oilchem_mongo_set_failed", error=str(exc))
            finally:
                wrapper.close()
        self.logger.info("oilchem token/cookie 已缓存", event="oilchem_token_saved", username=username, cacheKeys=self.safe_cache_key_info(username))

    def safe_cache_key_info(self, username: str) -> dict[str, str]:
        keys = OilchemCacheKeys.for_username(username)
        return {
            "redisUserTokenKey": keys.user_token_key,
            "redisCommonTokenKey": keys.common_token_key,
            "redisUserCookieKey": keys.user_cookie_key,
            "redisLegacyCookieKey": keys.legacy_cookie_key,
            "mongoName": keys.mongo_name,
        }

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()
