"""Platform-facing helpers.

crawler_platform_spiders is a passive runtime distribution.  It exposes
manifest/build contracts for crawler_platform to call, but it does not actively
register releases or store control-plane credentials. 不主动调用 crawler_platform 注册 Release。
"""

__all__: list[str] = []
