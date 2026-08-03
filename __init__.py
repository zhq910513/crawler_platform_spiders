from importlib.metadata import PackageNotFoundError, version

APP_NAME = "crawler_platform_spiders"

try:
    __version__ = version("crawler-platform-spiders")
except PackageNotFoundError:
    __version__ = "1.0.0"

__all__ = ["APP_NAME", "__version__"]
