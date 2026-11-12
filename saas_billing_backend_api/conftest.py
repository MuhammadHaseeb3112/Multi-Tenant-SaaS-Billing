import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """
    Throttle and login-lockout counters live in the cache; start every
    test with a clean one so tests don't throttle each other.
    """

    cache.clear()
    yield
    cache.clear()
