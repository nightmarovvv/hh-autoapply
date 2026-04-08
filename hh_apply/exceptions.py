"""Исключения hh-apply."""


class HHApplyError(Exception):
    """Базовое исключение."""


class NetworkError(HHApplyError):
    """Ошибка сети — стоит повторить."""


class AuthError(HHApplyError):
    """Требуется повторная авторизация."""


class RateLimitError(HHApplyError):
    """hh.ru ограничил частоту запросов — пауза."""


class DOMError(HHApplyError):
    """DOM изменился — селекторы устарели."""
