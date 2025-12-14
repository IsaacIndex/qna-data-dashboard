from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache, wraps
from typing import ParamSpec, TypeVar

try:
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - Streamlit unavailable during some tests
    st = None  # type: ignore[assignment]

P = ParamSpec("P")
T = TypeVar("T")


def cache_resource(func: Callable[P, T]) -> Callable[P, T]:
    """Decorate a function as a long-lived resource cache.

    Falls back to functools.lru_cache when Streamlit is not installed, enabling reuse
    across tests or CLI utilities outside the Streamlit runtime.
    """

    if st is not None and hasattr(st, "cache_resource"):
        return st.cache_resource(show_spinner=False)(func)

    cached_func = lru_cache(maxsize=None)(func)

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return cached_func(*args, **kwargs)

    wrapper.clear = cached_func.cache_clear  # type: ignore[attr-defined]
    return wrapper


def cache_data(func: Callable[P, T]) -> Callable[P, T]:
    """Decorate a function for cached data computations."""
    if st is not None and hasattr(st, "cache_data"):
        return st.cache_data(show_spinner=False)(func)

    cached_func = lru_cache(maxsize=128)(func)

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return cached_func(*args, **kwargs)

    wrapper.clear = cached_func.cache_clear  # type: ignore[attr-defined]
    return wrapper
