from __future__ import annotations

from crawler_foundation.core.exceptions import CaptchaOrRiskError


def parse_captcha_base64(img_base64: str, *, platform: str = "default", **kwargs) -> str:
    parser = kwargs.get("parser")
    if callable(parser):
        return str(parser(img_base64))
    raise CaptchaOrRiskError("验证码识别器未配置", details={"platform": platform})
